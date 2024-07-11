from typing import  Union, Optional, IO
import traceback
import io

import pandas as pd
import polars as pl
from upath import UPath

from mountainash_constants import CONST_DATAFILEFORMAT
from mountainash_utils_dataclasses import DataclassUtils
from mountainash_data import BaseDataFrame, DataFrameFactory
from mountainash_settings import SettingsParameters
from mountainash_auth_settings import get_auth_settings, AuthSettings

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.file_helpers import Base_FileHelper
from mountainash_utils_files.file_interface import get_file_helper_object




class FileReader:

    def __init__(self,
                 source_auth_parameters: SettingsParameters,
                 file_format:           str):

        if not source_auth_parameters :
            raise ValueError("FileReader: source_auth_parameters must be provided.")


        #FileFormat
        if not file_format or file_format not in DataclassUtils.get_enum_values_set(CONST_DATAFILEFORMAT):
            raise ValueError(f"Invalid file format: {file_format}. It should be set as DATA_FILE_FORMAT in your settings. Valid values are: {DataclassUtils.get_enum_values(CONST_DATAFILEFORMAT)}")
        
        #There will need to be a FileReaeder created for every source, so that the source_auth_parameters can be used to get the correct settings
        self.source_auth_parameters: SettingsParameters = source_auth_parameters
        self.source_auth_settings: AuthSettings = get_auth_settings(self.source_auth_parameters)
        self.source_storage_interface: Base_FileHelper = get_file_helper_object(source_auth_parameters)

        #File and dataframe formats
        self.file_format: str = file_format  
            
        #Ibis Backend
        self.db_interface = None


    def read_datafile(self, 
                      file_path: Union[UPath, str],
                    materialise:Optional[bool] = False,
                    decrypt:Optional[bool] = False,
                    decompress:Optional[bool] = False                      
                      ) -> Optional[BaseDataFrame]:
        

        u_file_path: UPath|None = PathHelper.format_path(path=file_path)

        if not self.source_storage_interface.path_exists(path=u_file_path):
            print(f"File not found: {u_file_path}")


        try:
            #Write the dataframe to the parquet file
            if self.file_format == CONST_DATAFILEFORMAT.PARQUET.value:
                df_datafile = self.read_parquet(file_path=file_path,
                                                materialise = materialise,
                                                decrypt = decrypt,
                                                decompress = decompress
                                                )       

            elif self.file_format == CONST_DATAFILEFORMAT.CSV.value:
                raise NotImplementedError
                # df_datafile = self.read_csv(file_path)                

            elif self.file_format == CONST_DATAFILEFORMAT.JSON.value:
                raise NotImplementedError
                # df_datafile = self.read_json(file_path)      

            else:
                raise ValueError(f"Unsupported file format: {self.file_format}")

            return df_datafile
              
        except Exception:
            print(f"Error reading data from file: {file_path}")
            print(traceback.format_exc())

            return None
        
    def read_xml_to_stream(self,
                source_file_path: Union[UPath, str], 
                decrypt: Optional[bool] = False,
                decompress: Optional[bool] = False
                ) -> IO:

        if source_file_path is None:
            raise ValueError("The report file is not set. Please set the report file before loading the report.")

        decrypt = bool(decrypt)
        decompress = bool(decompress)

        try:
            xml_report_file =  self.source_storage_interface.open_read_binarystream(source_path=source_file_path)

            if decrypt or decompress:

                processed_stream: io.BytesIO = self.source_storage_interface.process_source_stream(source_stream=xml_report_file, 
                                                            decrypt=decrypt, 
                                                            decompress=decompress)        
                return processed_stream
            else:
                return xml_report_file
                
        except Exception:
            raise ValueError(f"Error reading xml file: {source_file_path}")
            # print(traceback.format_exc())

            # return None



    def read_parquet(self, 
                     file_path: Union[UPath, str], 
                     materialise:Optional[bool] = False,
                     decrypt:Optional[bool] = False,
                     decompress:Optional[bool] = False
                     
                     ) -> Optional[BaseDataFrame]:

        u_file_path: UPath|None = PathHelper.format_path(path=file_path)

        if not u_file_path:
            raise ValueError(f"Invalid file path: {file_path}")

        #No point in returning a lazy frame if we are using pandas
        # if self.dataframe_framework == CONST_DATAFRAME_FRAMEWORK.PANDAS.value:
        #     materialise = True

        #Just retrieve the files with Polars
        polars_dataframe: Optional[Union[pl.DataFrame, pl.LazyFrame]] = None

        if decrypt or decompress:
            decrypt = bool(decrypt)
            decompress = bool(decompress)

            with self.source_storage_interface.open_read_binarystream(source_path=file_path) as parquet_stream:
                processed_stream: io.BytesIO = self.source_storage_interface.process_source_stream(source_stream=parquet_stream, 
                                                            decrypt=decrypt, 
                                                            decompress=decompress)
                polars_dataframe =  pl.read_parquet(source=processed_stream)

        if materialise:

            if self.source_storage_interface.supports_polars_native_read_parquet:
                #materialise the parquet file with native polars interface
                polars_dataframe =  pl.read_parquet(source=file_path, storage_options=self.source_storage_interface.get_connection_client_parameters())
            else:
                #Stream the file and materialise it with polars
                with self.source_storage_interface.open_read_binarystream(source_path=file_path) as parquet_stream:
                    polars_dataframe =  pl.read_parquet(source=parquet_stream)
     
        else:
            if self.source_storage_interface.supports_polars_native_read_parquet:
                #Native parquet reading on AWS, local S3, GCE can scan parquet files lazily
                polars_dataframe =  pl.scan_parquet(source=file_path, storage_options=self.source_storage_interface.get_connection_client_parameters())
            else:
                #Stream the file and materialise it with polars
                with self.source_storage_interface.open_read_binarystream(source_path=file_path) as parquet_stream:
                    polars_dataframe =  pl.read_parquet(source=parquet_stream)

        
        # if isinstance(polars_dataframe, pl.LazyFrame):
        #     polars_dataframe = polars_dataframe.collect()


        dataframe_object = DataFrameFactory.create_ibis_dataframe_object_from_dataframe(df=polars_dataframe)

        return dataframe_object
  


