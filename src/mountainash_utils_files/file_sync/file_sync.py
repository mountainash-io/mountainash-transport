import concurrent.futures as cf
import typing as t
from upath import UPath
from datetime import timedelta
from ibis import _

from mountainash_utils_files import FileInterface
from mountainash_settings import SettingsParameters
from mountainash_dataframes import IbisDataFrame, DataFrameUtils
from mountainash_dataframes.utils.dataframe_filters import FilterCondition as fc


# Assuming UPath is a class from a library you're using
# If not, you may need to adjust imports

class FileSyncer:
    """Handles file synchronization between storage locations"""

    @classmethod
    def put_file(cls,
                 source_settings_parameters: SettingsParameters,
                 destination_settings_parameters: SettingsParameters,
                 source_relative_path: str|UPath,
                 source_base_path: str|UPath,
                 destination_base_path: str|UPath,
                 dry_run: bool = False) -> bool:

        """Upload a file from source to destination"""
        source_filename = UPath(source_relative_path).parts[-1]
        destination_path = UPath(destination_base_path) / source_filename

        source_path = UPath(source_base_path) / source_relative_path

        if not dry_run:
            success = FileInterface().put_object_from_stream(
                destination_path=destination_path,
                source_path=source_path,
                obj_destination_settings=destination_settings_parameters,
                obj_source_settings=source_settings_parameters
            )
        else:
            success = True

        if success:
            print(f"{source_filename} successfully uploaded to {destination_path}")
        else:
            print(f"Unable to upload {source_filename} to {destination_path}")

        return success

    @classmethod
    def list_filenames(cls,
                    settings_parameters: SettingsParameters,
                    path: t.Any) -> t.List[UPath]:

        """List files from a specific path"""
        sources = FileInterface().list_sources(auth_parameters=settings_parameters, path=path, include_files=True, include_dirs=False)
        return [UPath(source).parts[-1] for source in sources]


    @classmethod
    def sync_files(cls,
                    source_settings_parameters: SettingsParameters,
                    destination_settings_parameters: SettingsParameters,
                    source_relative_paths: list,
                    source_base_path: str,
                    destination_path: str,
                    num_threads:    t.Optional[int] = 1,
                    dry_run: bool = False
                    ):

        """Sync files using single or multiple threads"""
        print(f"Copying files: {source_base_path}: {source_relative_paths}")

        if num_threads == 1:
            # Sequential processing
            for source_relative_path in source_relative_paths:
                cls.put_file(source_settings_parameters, destination_settings_parameters, source_relative_path, source_base_path,  destination_path, dry_run)
        else:
            # Parallel processing
            with cf.ThreadPoolExecutor(num_threads) as executor:
                futures = [
                    executor.submit(cls.put_file, source_settings_parameters, destination_settings_parameters, source_relative_path, source_base_path, destination_path, dry_run)
                    for source_relative_path in source_relative_paths
                ]
                for future in cf.as_completed(futures):
                    try:
                        future.result()  # To raise exceptions if any
                    except Exception as e:
                        print(f"Error processing file: {e}")

    @classmethod
    def get_filenames_from_paths(cls,
                    file_path_list: t.List[UPath|str]|UPath|str
                    ) -> list:

        if not isinstance(file_path_list, t.List):
            file_path_list = [file_path_list]

        filenames = [UPath(path).parts[-1] for path in file_path_list]
        return filenames


    #--------------------------
    @classmethod
    def get_unique_source_files(cls,
                    source_settings_parameters: SettingsParameters,
                    destination_settings_parameters: SettingsParameters,
                    source_path: t.Any,
                    destination_path: t.Any) -> list:

        """Get files that exist in source but not in destination"""

        source_files =      FileInterface().list_sources(auth_parameters=source_settings_parameters, path=source_path, include_files=True, include_dirs=False)
        destination_files = FileInterface().list_sources(auth_parameters=destination_settings_parameters, path=destination_path, include_files=True, include_dirs=False)
        # destination_files = cls.list_filenames(destination_settings_parameters, destination_path)

        # source_filenames = cls.get_filenames_from_paths(source_files)
        destination_filenames = cls.get_filenames_from_paths(destination_files)
        print(f"{source_path} source_files: {len(source_files)}")
        print(f"{destination_path} destination_filenames: {len(destination_filenames)}")

        return [source_file for source_file in source_files if UPath(source_file).parts[-1] not in destination_filenames]




    @classmethod
    def get_larger_source_files(cls,
                    source_settings_parameters: SettingsParameters,
                    destination_settings_parameters: SettingsParameters,
                    source_path: t.Any,
                    destination_path: t.Any) -> list:

        """Get files that exist in source but not in destination"""

        source = FileInterface().resolve_storage_object(auth_parameters=source_settings_parameters)
        dest = FileInterface().resolve_storage_object(auth_parameters=destination_settings_parameters)

        source_metadata = IbisDataFrame(DataFrameUtils.create_ibis_dataframe(source.get_file_metadata(source_path))).mutate(size_source = _.size).select(["full_path","size_source"])
        dest_metadata = IbisDataFrame(DataFrameUtils.create_ibis_dataframe(dest.get_file_metadata(destination_path))).mutate(size_dest = _.size).select(["full_path","size_dest"])

        filter_source_bigger = fc.col_gt("size_source", "size_dest")
        df_size_comparison = source_metadata.inner_join(dest_metadata, ["full_path"] ).mutate(source_bigger = _.size_source > _.size_dest).filter(filter_condition=filter_source_bigger)

        bigger_source_files = df_size_comparison.get_column_as_list("full_path")
        return bigger_source_files


    @classmethod
    def get_newer_source_files(cls,
                    source_settings_parameters: SettingsParameters,
                    destination_settings_parameters: SettingsParameters,
                    source_path: t.Any,
                    destination_path: t.Any,
                    newer_interval: timedelta
                    ) -> list:

        """Get files that exist in source but not in destination"""

        source = FileInterface().resolve_storage_object(auth_parameters=source_settings_parameters)
        dest = FileInterface().resolve_storage_object(auth_parameters=destination_settings_parameters)

        source_metadata = (IbisDataFrame(DataFrameUtils.create_ibis_dataframe(source.get_file_metadata(source_path)))
                            .mutate(last_modified_source_str = _.last_modified.cast("str").substr(0,26)).select(["full_path","last_modified_source_str"])
        )
        dest_metadata = ( IbisDataFrame(DataFrameUtils.create_ibis_dataframe(dest.get_file_metadata(destination_path)))
                            .mutate(last_modified_dest_str = _.last_modified.cast("str").substr(0,26)).select(["full_path","last_modified_dest_str"])
        )


        newer_interval_seconds = newer_interval.total_seconds()
        filter_source_newer = fc.gt("last_modified_difference_seconds", newer_interval_seconds)

        df_last_modified_comparison = ( source_metadata.inner_join(dest_metadata, ["full_path"] )
                                    .mutate(last_modified_difference_seconds = (_.last_modified_source_str.as_timestamp("%Y-%m-%d %H:%M:%S.%f") -
                                                                                _.last_modified_dest_str.as_timestamp("%Y-%m-%d %H:%M:%S.%f")).cast(int)/1000000
                                            )
                                    .filter(filter_condition=filter_source_newer)
        )

        newer_source_files = df_last_modified_comparison.get_column_as_list("full_path")
        return newer_source_files





    @classmethod
    def resolve_source_files_list(cls,
                    source_settings_parameters: SettingsParameters,
                    destination_settings_parameters: SettingsParameters,
                    source_path: t.Any,
                    destination_path: t.Any,
                    copy_all:       t.Optional[bool] =False,
                    copy_unique:    t.Optional[bool] =False,
                    copy_larger:    t.Optional[bool] =False,
                    copy_newer:     t.Optional[bool] =False,
                    newer_interval: t.Optional[timedelta] = timedelta(minutes=720),

                    ) -> list:


        final_source_filepaths  = []

        if copy_all:
            final_source_filepaths = FileInterface().list_sources(auth_parameters=source_settings_parameters, path=source_path, include_files=True, include_dirs=False)

            print(f"resolve_source_files_list. final_source_filepaths:{len(final_source_filepaths)}")

        else:

            unique_source_filepaths = cls.get_unique_source_files(source_settings_parameters=source_settings_parameters,
                                                                             destination_settings_parameters=destination_settings_parameters,
                                                                             source_path=source_path,
                                                                             destination_path=destination_path) if copy_unique else []

            larger_source_filepaths = cls.get_larger_source_files(source_settings_parameters=source_settings_parameters,
                                                                             destination_settings_parameters=destination_settings_parameters,
                                                                            source_path=source_path,
                                                                            destination_path=destination_path) if copy_larger else []

            newer_source_filepaths = cls.get_newer_source_files( source_settings_parameters=source_settings_parameters,
                                                                            destination_settings_parameters=destination_settings_parameters,
                                                                            source_path=source_path,
                                                                            destination_path=destination_path,
                                                                            newer_interval=newer_interval) if copy_newer else []

            final_source_filepaths = list(set(unique_source_filepaths + larger_source_filepaths + newer_source_filepaths))

            print(f"resolve_source_files_list. unique_source_filepaths:{len(unique_source_filepaths)} larger_source_filepaths:{len(larger_source_filepaths)}  newer_source_filepaths:{len(newer_source_filepaths)} ")


        return final_source_filepaths
