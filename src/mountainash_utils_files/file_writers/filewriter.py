
from typing import  Union, Any, Optional
import io
import traceback

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from xsdata.formats.dataclass.serializers import XmlSerializer
from upath import UPath

from mountainash_constants import CONST_DATAFILEFORMAT
from mountainash_settings import SettingsParameters
from mountainash_auth_settings import  AuthSettings, get_auth_settings
from mountainash_utils_dataclasses import  DataclassUtils
from mountainash_utils_dataframes import   DataFrameUtils, BaseDataFrame
from mountainash_utils_files.path_helpers import PathHelper



from ..file_helpers import Base_FileHelper
from ..file_interface import get_file_helper_object

class FileWriter:
    """
    A class for writing data to a file using a specified filesystem and file format.

    Args:
        filesystem (str): The name of the filesystem to use for writing the file.
        file_format (str): The format of the file to be written.

    Raises:
        ValueError: If an invalid filesystem or file format is provided.

    Attributes:
        filesystem (str): The name of the filesystem being used for writing the file.
        file_format (str): The format of the file being written.
        filesystem_interface (FilesystemInterface): An instance of the FilesystemInterface class for the specified filesystem.
    """

    def __init__(self, 
                #  app_settings_parameters: SettingsParameters,
                 destination_auth_parameters: SettingsParameters,
                 file_format:str):


        # if not app_settings_parameters:
        #     raise ValueError("ReportBuildOrchestrator: app_settings_parameters must be provided.")

        # #App Settings
        # self.app_settings_parameters: SettingsParameters  = app_settings_parameters


        #FileSystem
        # if not filesystem or filesystem not in DataclassUtils.get_enum_values_set(CONST_FILESYSTEM):
        #     raise ValueError(f"Invalid filesystem: {filesystem}")

        #FileFormat

        if file_format and file_format not in DataclassUtils.get_enum_values_set(CONST_DATAFILEFORMAT):
            raise ValueError(f"Invalid file format: {file_format}")
        
        #There will need to be a FileReaeder created for every source, so that the source_auth_parameters can be used to get the correct settings
        self.destination_auth_parameters: SettingsParameters = destination_auth_parameters
        self.destination_auth_settings: AuthSettings = get_auth_settings(self.destination_auth_parameters)
        self.destination_storage_interface: Base_FileHelper = get_file_helper_object(destination_auth_parameters)


        # self.filesystem =   filesystem  
        self.file_format =  file_format  
        # self.filesystem_interface = FilesystemInterface(self.filesystem)



    def write_datafile(self, 
                       df_datafile: BaseDataFrame, 
                       output_file_path: Union[UPath, str],
                       overwrite: Optional[bool] = False,
                       encrypt: Optional[bool] = False,
                       compress: Optional[bool] = False,
                       
                       ) -> bool:

        # determine:
        # persistence as a file or database - in orchestrator
        # file system and url prexix - 
        # file format - function call, default in config
        # source dataframe format - runtime
        # test on s3, local, memory, azure, gcs
        # also support uploading to a database

        u_output_file_path: UPath | None = PathHelper.format_path(output_file_path)
        if not u_output_file_path:
            print(f"Invalid file path: {output_file_path}")
            return False

        try:
            #Write the dataframe to the parquet file
            if self.file_format == CONST_DATAFILEFORMAT.PARQUET.value:
                self.write_parquet(dataframe=df_datafile, output_file_path=u_output_file_path, overwrite=overwrite, encrypt=encrypt, compress=compress)     

            elif self.file_format == CONST_DATAFILEFORMAT.CSV.value:
                # raise NotImplementedError
                self.write_csv(dataframe=df_datafile, output_file_path=output_file_path, overwrite=overwrite, encrypt=encrypt, compress=compress)                
            elif self.file_format == CONST_DATAFILEFORMAT.JSON.value:
                # raise NotImplementedError
                self.write_json(dataframe=df_datafile, output_file_path=output_file_path, overwrite=overwrite, encrypt=encrypt, compress=compress)      
            elif self.file_format == CONST_DATAFILEFORMAT.DELTA.value:
                raise NotImplementedError
                # self.write_delta(df_datafile, output_file_path)      

            else:
                print(f"Unsupported file format: {self.file_format}")
                return False  
            
            return True  
                
        except Exception:
            print(f"Error writing data to file: {output_file_path}")
            print(traceback.format_exc())
            return False
        


    def write_parquet(self, 
                      dataframe: BaseDataFrame,
                      output_file_path: UPath, 
                      overwrite: Optional[bool] = True,
                      encrypt: Optional[bool] = False,
                      compress: Optional[bool] = False,
                      **kwargs) -> bool:
            

        u_output_file_path: UPath | None = PathHelper.format_path(path=output_file_path)
        if not u_output_file_path:
            raise ValueError("Invalid file path")


        destination_exists: bool =  self.destination_storage_interface.path_exists(path=u_output_file_path)
        if destination_exists and overwrite is False:
            print(f"File {u_output_file_path} already exists. Overwrite is set to {overwrite}")
            return False

        if not self.destination_storage_interface.path_parent_exists(path=u_output_file_path):
            self.destination_storage_interface.prepare_path_parent(path=u_output_file_path)


        pd_dataframe: pd.DataFrame = DataFrameUtils.cast_dataframe_to_pandas(df_dataframe=dataframe.df)
        pa_dataframe: Any = pa.Table.from_pandas(pd_dataframe)

   
        if encrypt or compress:

            encrypt = bool(encrypt)
            compress = bool(compress)

            #Write the dataframe to a temporary stream in parquet
            with io.BytesIO() as temp_stream:

                pq.write_table(table=pa_dataframe, where=temp_stream, compression="snappy")
                processed_stream: io.BytesIO = self.destination_storage_interface.process_source_stream(source_stream=temp_stream, encrypt=encrypt, decrypt=compress)

                with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as parquet_output_stream:
                    parquet_output_stream.write(processed_stream.read())
            return True
        
        else:

            with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as parquet_output_stream:
                pq.write_table(table=pa_dataframe, where=parquet_output_stream, compression="snappy")                

            return True




    def write_csv(self, 
                  dataframe: BaseDataFrame, 
                  output_file_path: Union[str, UPath],
                      overwrite: Optional[bool] = True,
                      encrypt: Optional[bool] = False,
                      compress: Optional[bool] = False
                      ):

        u_output_file_path: UPath | None = PathHelper.format_path(output_file_path)
        if not u_output_file_path:
            raise ValueError("Invalid file path")


        destination_exists: bool =  self.destination_storage_interface.path_exists(path=u_output_file_path)
        if destination_exists and overwrite is False:
            print(f"File {u_output_file_path} already exists. Overwrite is set to {overwrite}")
            return False

        if not self.destination_storage_interface.path_parent_exists(path=u_output_file_path):
            self.destination_storage_interface.prepare_path_parent(path=u_output_file_path)


        #Convert to pandas dataframe
        pd_dataframe: pd.DataFrame = DataFrameUtils.cast_dataframe_to_pandas(dataframe.df)

        if encrypt or compress:

            encrypt = bool(encrypt)
            compress = bool(compress)

            #Write the dataframe to a temporary stream in parquet
            with io.BytesIO() as temp_stream:

                pd_dataframe.to_csv(temp_stream, index=False)
                processed_stream: io.BytesIO = self.destination_storage_interface.process_source_stream(source_stream=temp_stream, encrypt=encrypt, decrypt=compress)

                with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as csv_output_stream:
                    csv_output_stream.write(processed_stream.read())
            return True
        
        else:

            with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as csv_output_stream:
                pd_dataframe.to_csv(path_or_buf=csv_output_stream, index=False)

            return True


    def write_json(self, 
                   dataframe: BaseDataFrame, 
                   output_file_path: Union[str, UPath],
                   overwrite: Optional[bool] = True,
                   encrypt: Optional[bool] = False,
                   compress: Optional[bool] = False
                   ):

        u_output_file_path: UPath | None = PathHelper.format_path(output_file_path)
        if not u_output_file_path:
            raise ValueError("Invalid file path")

        destination_exists: bool =  self.destination_storage_interface.path_exists(path=u_output_file_path)
        if destination_exists and overwrite is False:
            print(f"File {u_output_file_path} already exists. Overwrite is set to {overwrite}")
            return False

        if not self.destination_storage_interface.path_parent_exists(path=u_output_file_path):
            self.destination_storage_interface.prepare_path_parent(path=u_output_file_path)


        #Convert to pandas dataframe
        pd_dataframe: pd.DataFrame = DataFrameUtils.cast_dataframe_to_pandas(dataframe.df)

        #Convert to pandas dataframe
        pd_dataframe: pd.DataFrame = DataFrameUtils.cast_dataframe_to_pandas(dataframe.df)

        if encrypt or compress:

            encrypt = bool(encrypt)
            compress = bool(compress)

            #Write the dataframe to a temporary stream in parquet
            with io.StringIO() as temp_stream:

                pd_dataframe.to_json(path_or_buf=temp_stream, orient="records", lines=True)
                processed_stream: io.BytesIO = self.destination_storage_interface.process_source_stream(source_stream=temp_stream, encrypt=encrypt, decrypt=compress)

                with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as json_output_stream:
                    json_output_stream.write(processed_stream.read())
            return True
        
        else:
            
            with self.destination_storage_interface.open_write_binarystream(destination_path=u_output_file_path) as json_output_stream:
                pd_dataframe.to_json(path_or_buf=json_output_stream, orient="records", lines=True)

            return True


    def write_delta(self, 
                    df_datafile: BaseDataFrame, 
                    output_file_path: Union[str, UPath],
                         overwrite:bool = True,
                      encrypt: Optional[bool] = False,
                      compress: Optional[bool] = False
                      ):
        
        raise NotImplementedError
        # output_file_path = UPath(output_file_path)

        # df: pd.DataFrame = DataframeUtils.cast_dataframe_to_pandas(df_datafile)
        # # TODO: Writing to delta format requires DeltaLake
        # # You need to install delta package with `pip install delta`
        # # and also, PySpark might be required.
        # # import delta
        
        # with output_file_path.open("wb") as f:
        #     df.to_delta(f)

    # def get_xml_serializer(self, models_package:str) -> XmlSerializer:


    #     app_settings: AppSettings = get_app_settings(app_settings_parameters=self.app_settings_parameters)

    #     #TODO: This cannot be here!
    #     version_map: Dict[str, str] = DataclassUtils.get_enum_values_dict_reverse_lookup(enumclass=CONST_ACRDS_RESPONSE_XML_SCHEMA_FILE, keyenumclass=CONST_ACRDS_VERSION)
    #     schema_location: Optional[str] = version_map.get(app_settings.BATCH_VERSION)


    #     xmlcontext = XmlContext(models_package = models_package)
    

    #     xmlconfig = SerializerConfig(
    #         xml_declaration=True, 
    #         xml_version="1.0", 
    #         encoding="UTF-8",
    #         no_namespace_schema_location=schema_location,
    #         pretty_print=True
    #     )

    #     serializer = XmlSerializer(config= xmlconfig, 
    #                                context= xmlcontext)

    #     return serializer

    def write_xml_object(self, 
                         xmlobj, 
                         xml_serializer: XmlSerializer, 
                         xml_output_filepath: Union[UPath, str],
                         overwrite: Optional[bool] = True,
                         encrypt: Optional[bool] = False,
                         compress: Optional[bool] = False) -> bool:


        
        u_xml_output_filepath: UPath | None = PathHelper.format_path(path=xml_output_filepath)
        if not u_xml_output_filepath:
            raise ValueError("Invalid file path")

        encrypt = bool(encrypt)
        compress = bool(compress)

        #Establish whether the destination is writable
        destination_exists: bool =  self.destination_storage_interface.path_exists(path=u_xml_output_filepath)
        if destination_exists and overwrite is False:
            print(f"File {u_xml_output_filepath} already exists. Overwrite is set to {overwrite}")
            return False
        
        if not self.destination_storage_interface.path_parent_exists(path=u_xml_output_filepath):
            self.destination_storage_interface.prepare_path_parent(path=u_xml_output_filepath)


        #serializer: XmlSerializer = self.get_xml_serializer(models_package="mountainash_acrds_core.report.report_dataclasses")  

        #write file to disk:

        if encrypt or compress:

            with self.destination_storage_interface.open_write_binarystream(destination_path=u_xml_output_filepath) as output_binary_file:

                #Write the dataframe to a temporary stream in parquet
                with io.StringIO() as temp_stream:
                    
                    #write to a temp stream
                    xml_serializer.write(out=temp_stream, obj=xmlobj)
                    processed_stream: io.BytesIO = self.destination_storage_interface.process_source_stream(source_stream=temp_stream, encrypt=encrypt, decrypt=compress)

                    output_binary_file.write(processed_stream.read())

                return True
        
        else:
            with self.destination_storage_interface.open_write_textstream(destination_path=u_xml_output_filepath) as output_text_file:

                #if isinstance(output_text_file, TextIO):
                xml_serializer.write(out=output_text_file, obj=xmlobj)
                #else:
                #    raise ValueError("Invalid file stream")


        xml_output_filestr = PathHelper.path_to_str(u_xml_output_filepath)
        
        print(f"Writing XML file to {xml_output_filestr}")
        return True

