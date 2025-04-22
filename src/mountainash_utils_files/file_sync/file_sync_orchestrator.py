import concurrent.futures as cf
import typing as t
from upath import UPath
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from mountainash_utils_files import FileInterface
from mountainash_settings import SettingsParameters, get_settings

from . import FileSyncer

from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE

# Assuming UPath is a class from a library you're using
# If not, you may need to adjust imports
 
class FileSyncOrchestrator:

    @classmethod
    def sync_course_results_by_country(cls,
                            country_id: str, 
                            source_settings_parameters: SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path: str|UPath,
                            destination_base_path: str|UPath,
                            num_threads:    t.Optional[int]  =1, 
                            dry_run:        t.Optional[bool] =True,
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720)
                            ) -> None:


        if get_settings(source_settings_parameters).PROVIDER_TYPE in [CONST_STORAGE_PROVIDER_TYPE.R2, CONST_STORAGE_PROVIDER_TYPE.S3]:

            cls._sync_course_results_by_country_cloud_source(country_id=country_id,

                                                            source_settings_parameters=source_settings_parameters,
                                                            destination_settings_parameters=destination_settings_parameters,

                                                            source_path=source_base_path,
                                                            destination_path=destination_base_path,
                                                            
                                                            copy_all=copy_all,
                                                            copy_unique=copy_unique,
                                                            copy_larger=copy_larger,
                                                            copy_newer=copy_newer,
                                                            newer_interval=newer_interval
                                                            )


        if get_settings(source_settings_parameters).PROVIDER_TYPE in [CONST_STORAGE_PROVIDER_TYPE.LOCAL]:

            cls._sync_course_results_by_country_local_source(country_id=country_id,

                                                            source_settings_parameters=source_settings_parameters,
                                                            destination_settings_parameters=destination_settings_parameters,
            
                                                            source_path=source_base_path,
                                                            destination_path=destination_base_path,
            
                                                            copy_all=copy_all,
                                                            copy_unique=copy_unique,
                                                            copy_larger=copy_larger,
                                                            copy_newer=copy_newer,
                                                            newer_interval=newer_interval)

        return None

    @classmethod
    def _sync_course_results_by_country_local_source(cls,
                            country_id: str, 
                            source_settings_parameters: SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path: str|UPath,
                            destination_base_path: str|UPath,
                            num_threads: t.Optional[int]=1, 
                            dry_run:        t.Optional[bool]=True,
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720),
                            ) -> None:

        if dry_run:
            print("--------- DRY RUN !! ----------")


        source_country_path =            UPath(source_base_path) / "results" / f"country_id={country_id}/" 

        course_paths = FileInterface().list_sources(auth_parameters=source_settings_parameters, path=source_country_path, include_files=False, include_dirs=True)
        source_result_dirpaths_course = [dirpath.parts[-1]for dirpath in course_paths]

        print(source_result_dirpaths_course)

        for course_path in source_result_dirpaths_course:

            source_path =            UPath(source_base_path) / "results" / f"country_id={country_id}" / course_path
            destination_path = UPath(destination_base_path) / "results" / f"country_id={country_id}" / course_path

            source_relative_filepaths = FileSyncer.resolve_source_files_list(source_settings_parameters=source_settings_parameters,
                                                destination_settings_parameters=destination_settings_parameters,

                                                source_path=source_path,
                                                destination_path=destination_path,


                                                copy_all=copy_all,
                                                copy_unique=copy_unique,
                                                copy_larger=copy_larger,
                                                copy_newer=copy_newer,
                                                newer_interval=newer_interval)

            if len(source_relative_filepaths) > 0:
                print(f"Copying unique files: {source_relative_filepaths}")

                FileSyncer.sync_files(source_settings_parameters=source_settings_parameters,
                                                    destination_settings_parameters=destination_settings_parameters,
                                                    source_relative_paths=source_relative_filepaths, 
                                                    source_base_path=source_base_path, 
                                                    destination_path=destination_path,
                                                    num_threads=num_threads,
                                                    dry_run=dry_run
                                                    )
            else:
                print("All source files are already on th destination")

        return None


    @classmethod
    def _sync_course_results_by_country_cloud_source(cls,
                            country_id: str, 
                            source_settings_parameters: SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path: str|UPath,
                            destination_base_path: str|UPath,
                            num_threads: t.Optional[int]=1, 
                            dry_run:        t.Optional[bool]=True,
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720),

                            ) -> None:

        if dry_run:
            print("--------- DRY RUN !! ----------")

        source_path =            UPath(source_base_path) / "results" / f"country_id={country_id}" 
        destination_path = UPath(destination_base_path) / "results" / f"country_id={country_id}" 


        source_relative_filepaths = FileSyncer.resolve_source_files_list(source_settings_parameters=source_settings_parameters,
                                                destination_settings_parameters=destination_settings_parameters,

                                                source_path=source_path,
                                                destination_path=destination_path,


                                                copy_all=copy_all,
                                                copy_unique=copy_unique,
                                                copy_larger=copy_larger,
                                                copy_newer=copy_newer,
                                                newer_interval=newer_interval)

        if len(source_relative_filepaths) > 0:
            print(f"Copying unique files: {source_relative_filepaths}")

            FileSyncer.sync_files(  source_settings_parameters=source_settings_parameters,
                                    destination_settings_parameters=destination_settings_parameters,
                                    source_relative_paths=source_relative_filepaths, 
                                    source_base_path=source_base_path, 
                                    destination_path=destination_path,
                                    num_threads=num_threads,
                                    dry_run=dry_run,
                                     )
        else:
            print("All source files are already on th destination")

        return None



    @classmethod
    def sync_country_events(cls,
                            country_id: str,
                            source_settings_parameters:     SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path:       str|UPath,
                            destination_base_path:  str|UPath,
                            num_threads:    t.Optional[int]=1,
                            dry_run:        t.Optional[bool]=True,
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720),

                           ) -> None:

        if dry_run:
            print("--------- DRY RUN !! ----------")

        source_path =      UPath(source_base_path) / "events" / f"country_id={country_id}" 
        destination_path = UPath(destination_base_path) / "events" / f"country_id={country_id}" 


        source_relative_filepaths = FileSyncer.resolve_source_files_list(source_settings_parameters=source_settings_parameters,
                                                destination_settings_parameters=destination_settings_parameters,

                                                source_path=source_path,
                                                destination_path=destination_path,

                                                copy_all=copy_all,
                                                copy_unique=copy_unique,
                                                copy_larger=copy_larger,
                                                copy_newer=copy_newer,
                                                newer_interval=newer_interval)

        if len(source_relative_filepaths) > 0:
            print(f"Copying unique files: {source_relative_filepaths}")

            FileSyncer.sync_files(  source_settings_parameters=source_settings_parameters,
                                    destination_settings_parameters=destination_settings_parameters,
                                    source_relative_paths=source_relative_filepaths, 
                                    source_base_path=source_base_path, 
                                    destination_path=destination_path,
                                    num_threads=num_threads,
                                    dry_run=dry_run,
                                     )
        else:
            print("All source files are already on th destination")

        return None



    @classmethod
    def sync_courses(cls,
                            source_settings_parameters: SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path: str|UPath,
                            destination_base_path: str|UPath,
                            num_threads: t.Optional[int]=1, 
                            dry_run:        t.Optional[bool]=True,
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720),
                            
                            
                            ) -> None:

        if dry_run:
            print("--------- DRY RUN !! ----------")

        source_path =            UPath(source_base_path) / "courses" / "courses.parquet" 
        destination_path = UPath(destination_base_path) / "courses"  

        source_relative_filepaths = FileSyncer.resolve_source_files_list(source_settings_parameters=source_settings_parameters,
                                                destination_settings_parameters=destination_settings_parameters,

                                                source_path=source_path,
                                                destination_path=destination_path,

                                                copy_all=copy_all,
                                                copy_unique=copy_unique,
                                                copy_larger=copy_larger,
                                                copy_newer=copy_newer,
                                                newer_interval=newer_interval)     
                                                
                                                

        if len(source_relative_filepaths) > 0:
            print(f"Copying unique files: {source_relative_filepaths}")

            FileSyncer.sync_files(  source_settings_parameters=source_settings_parameters,
                                    destination_settings_parameters=destination_settings_parameters,
                                    source_relative_paths=source_relative_filepaths, 
                                    source_base_path=source_base_path, 
                                    destination_path=destination_path,
                                    num_threads=num_threads,
                                    dry_run=dry_run,
                                     )
        else:
            print("No source files found")

        return None


    @classmethod
    def sync_countries(cls,
                            source_settings_parameters: SettingsParameters,
                            destination_settings_parameters: SettingsParameters,
                            source_base_path: str|UPath,
                            destination_base_path: str|UPath,
                            num_threads:    t.Optional[int]  =1, 
                            dry_run:        t.Optional[bool] =True, 
                            copy_all:       t.Optional[bool] =False,
                            copy_unique:    t.Optional[bool] =False,
                            copy_larger:    t.Optional[bool] =False,
                            copy_newer:     t.Optional[bool] =False,
                            newer_interval: t.Optional[timedelta] = timedelta(minutes=720),
                            
                            ) -> None:

        if dry_run:
            print("--------- DRY RUN !! ----------")

        source_path =            UPath(source_base_path) / "countries"  / "countries.parquet" 
        destination_path = UPath(destination_base_path) / "countries" 

        # ---------------------------------
        # Unique Source files - Just get the file on source.
        # source_relative_filepaths = FileInterface().list_sources(auth_parameters=source_settings_parameters, path=source_path, include_files=True, include_dirs=False)

        source_relative_filepaths = FileSyncer.resolve_source_files_list(source_settings_parameters=source_settings_parameters,
                                                destination_settings_parameters=destination_settings_parameters,

                                                source_path=source_path,
                                                destination_path=destination_path,


                                                copy_all=copy_all,
                                                copy_unique=copy_unique,
                                                copy_larger=copy_larger,
                                                copy_newer=copy_newer,
                                                newer_interval=newer_interval)

        if len(source_relative_filepaths) > 0:
            print(f"Copying unique files: {source_relative_filepaths}")

            FileSyncer.sync_files(  source_settings_parameters=source_settings_parameters,
                                    destination_settings_parameters=destination_settings_parameters,
                                    source_relative_paths=source_relative_filepaths, 
                                    source_base_path=source_base_path, 
                                    destination_path=destination_path,
                                    num_threads=num_threads,
                                    dry_run=dry_run,
                                     )
        else:
            print("No source files found")

        return None
