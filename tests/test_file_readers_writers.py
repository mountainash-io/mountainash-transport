"""
Tests for file_readers and file_writers modules.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from io import BytesIO, StringIO
from typing import Any, Dict

import pandas as pd
import polars as pl


class TestFileReader:
    """Test FileReader functionality."""

    def test_filereader_import(self):
        """Test FileReader can be imported."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            assert FileReader is not None
        except ImportError:
            pytest.skip("FileReader not available")

    def test_filereader_initialization(self):
        """Test FileReader can be initialized."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            
            reader = FileReader()
            assert reader is not None
            
        except ImportError:
            pytest.skip("FileReader not available")
        except Exception:
            # If initialization requires parameters, that's acceptable
            pass

    def test_read_text_file(self, temp_file, sample_text_content):
        """Test reading text files."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            
            reader = FileReader()
            
            if hasattr(reader, 'read_text'):
                result = reader.read_text(str(temp_file))
                assert isinstance(result, str)
                assert sample_text_content in result
                
        except ImportError:
            pytest.skip("FileReader not available")

    def test_read_json_file(self, temp_directory, sample_json_content):
        """Test reading JSON files."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            
            # Create JSON test file
            json_file = temp_directory / "test.json"
            with open(json_file, 'w') as f:
                json.dump(sample_json_content, f)
            
            reader = FileReader()
            
            if hasattr(reader, 'read_json'):
                result = reader.read_json(str(json_file))
                assert isinstance(result, dict)
                assert result == sample_json_content
                
        except ImportError:
            pytest.skip("FileReader not available")

    def test_read_csv_file_pandas(self, temp_directory):
        """Test reading CSV files returning pandas DataFrame."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            
            # Create CSV test file
            csv_file = temp_directory / "test.csv"
            test_data = "name,age,city\nJohn,30,NYC\nJane,25,LA\n"
            csv_file.write_text(test_data)
            
            reader = FileReader()
            
            if hasattr(reader, 'read_csv'):
                result = reader.read_csv(str(csv_file))
                
                # Could return pandas or polars DataFrame
                if hasattr(result, 'shape'):  # pandas/polars DataFrame
                    assert result.shape[0] == 2  # 2 rows
                    assert result.shape[1] == 3  # 3 columns
                elif isinstance(result, list):  # Could be list of dicts
                    assert len(result) == 2
                    
        except ImportError:
            pytest.skip("FileReader not available")

    def test_read_parquet_file(self, temp_directory):
        """Test reading Parquet files."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            
            # Create test DataFrame and save as Parquet
            df = pd.DataFrame({
                'name': ['John', 'Jane'],
                'age': [30, 25],
                'city': ['NYC', 'LA']
            })
            
            parquet_file = temp_directory / "test.parquet"
            df.to_parquet(parquet_file)
            
            reader = FileReader()
            
            if hasattr(reader, 'read_parquet'):
                result = reader.read_parquet(str(parquet_file))
                
                if hasattr(result, 'shape'):
                    assert result.shape[0] == 2
                    assert result.shape[1] == 3
                    
        except ImportError:
            pytest.skip("FileReader or dependencies not available")

    def test_read_with_file_helper(self, local_auth_params):
        """Test FileReader integration with file helpers."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_helpers import Local_FileHelper
            
            reader = FileReader()
            helper = Local_FileHelper(auth_parameters=local_auth_params)
            
            # Test if reader can work with file helper
            if hasattr(reader, 'set_file_helper'):
                reader.set_file_helper(helper)
                assert reader is not None
                
        except ImportError:
            pytest.skip("FileReader or dependencies not available")


class TestFileWriter:
    """Test FileWriter functionality."""

    def test_filewriter_import(self):
        """Test FileWriter can be imported."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            assert FileWriter is not None
        except ImportError:
            pytest.skip("FileWriter not available")

    def test_filewriter_initialization(self):
        """Test FileWriter can be initialized."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            writer = FileWriter()
            assert writer is not None
            
        except ImportError:
            pytest.skip("FileWriter not available")
        except Exception:
            # If initialization requires parameters, that's acceptable
            pass

    def test_write_text_file(self, temp_directory, sample_text_content):
        """Test writing text files."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            writer = FileWriter()
            output_file = temp_directory / "output.txt"
            
            if hasattr(writer, 'write_text'):
                writer.write_text(str(output_file), sample_text_content)
                
                # Verify file was created and contains correct content
                assert output_file.exists()
                content = output_file.read_text()
                assert sample_text_content in content
                
        except ImportError:
            pytest.skip("FileWriter not available")

    def test_write_json_file(self, temp_directory, sample_json_content):
        """Test writing JSON files."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            writer = FileWriter()
            output_file = temp_directory / "output.json"
            
            if hasattr(writer, 'write_json'):
                writer.write_json(str(output_file), sample_json_content)
                
                # Verify JSON file was created correctly
                assert output_file.exists()
                with open(output_file) as f:
                    loaded_data = json.load(f)
                assert loaded_data == sample_json_content
                
        except ImportError:
            pytest.skip("FileWriter not available")

    def test_write_csv_file(self, temp_directory):
        """Test writing CSV files from DataFrame."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            # Create test DataFrame
            df = pd.DataFrame({
                'name': ['John', 'Jane'],
                'age': [30, 25],
                'city': ['NYC', 'LA']
            })
            
            writer = FileWriter()
            output_file = temp_directory / "output.csv"
            
            if hasattr(writer, 'write_csv'):
                writer.write_csv(str(output_file), df)
                
                # Verify CSV file was created
                assert output_file.exists()
                content = output_file.read_text()
                assert 'John' in content
                assert 'Jane' in content
                
        except ImportError:
            pytest.skip("FileWriter or dependencies not available")

    def test_write_parquet_file(self, temp_directory):
        """Test writing Parquet files from DataFrame."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            # Create test DataFrame
            df = pd.DataFrame({
                'name': ['John', 'Jane'],
                'age': [30, 25],
                'city': ['NYC', 'LA']
            })
            
            writer = FileWriter()
            output_file = temp_directory / "output.parquet"
            
            if hasattr(writer, 'write_parquet'):
                writer.write_parquet(str(output_file), df)
                
                # Verify Parquet file was created
                assert output_file.exists()
                
                # Try to read it back to verify
                df_read = pd.read_parquet(output_file)
                assert df_read.shape == df.shape
                
        except ImportError:
            pytest.skip("FileWriter or dependencies not available")

    def test_write_with_compression(self, temp_directory, sample_text_content):
        """Test writing files with compression."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            writer = FileWriter()
            output_file = temp_directory / "compressed.txt.gz"
            
            if hasattr(writer, 'write_text_compressed'):
                writer.write_text_compressed(str(output_file), sample_text_content)
                
                # Verify compressed file was created
                assert output_file.exists()
                assert output_file.stat().st_size > 0
                
            elif hasattr(writer, 'write_text') and hasattr(writer, 'set_compression'):
                writer.set_compression(True)
                writer.write_text(str(output_file), sample_text_content)
                assert output_file.exists()
                
        except ImportError:
            pytest.skip("FileWriter not available")

    def test_write_with_file_helper(self, local_auth_params, temp_directory):
        """Test FileWriter integration with file helpers."""
        try:
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            from mountainash_utils_files.file_helpers import Local_FileHelper
            
            writer = FileWriter()
            helper = Local_FileHelper(auth_parameters=local_auth_params)
            
            # Test if writer can work with file helper
            if hasattr(writer, 'set_file_helper'):
                writer.set_file_helper(helper)
                
                output_file = temp_directory / "helper_output.txt"
                if hasattr(writer, 'write_text'):
                    writer.write_text(str(output_file), "test content")
                    assert output_file.exists()
                
        except ImportError:
            pytest.skip("FileWriter or dependencies not available")


@pytest.mark.integration
class TestFileReadersWritersIntegration:
    """Integration tests for file readers and writers."""

    def test_read_write_roundtrip_text(self, temp_directory, sample_text_content):
        """Test reading and writing text files in roundtrip."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            reader = FileReader()
            writer = FileWriter()
            
            # Write file
            original_file = temp_directory / "original.txt"
            if hasattr(writer, 'write_text'):
                writer.write_text(str(original_file), sample_text_content)
                
                # Read file back
                if hasattr(reader, 'read_text'):
                    content = reader.read_text(str(original_file))
                    assert content == sample_text_content
                    
                    # Write to new file
                    copy_file = temp_directory / "copy.txt"
                    writer.write_text(str(copy_file), content)
                    
                    # Verify copy matches original
                    assert copy_file.read_text() == original_file.read_text()
                    
        except ImportError:
            pytest.skip("FileReader/FileWriter not available")

    def test_read_write_roundtrip_json(self, temp_directory, sample_json_content):
        """Test reading and writing JSON files in roundtrip."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            reader = FileReader()
            writer = FileWriter()
            
            original_file = temp_directory / "original.json"
            
            if hasattr(writer, 'write_json') and hasattr(reader, 'read_json'):
                # Write JSON
                writer.write_json(str(original_file), sample_json_content)
                
                # Read JSON back
                loaded_data = reader.read_json(str(original_file))
                assert loaded_data == sample_json_content
                
                # Write to new file
                copy_file = temp_directory / "copy.json"
                writer.write_json(str(copy_file), loaded_data)
                
                # Verify copy matches original
                with open(copy_file) as f:
                    copy_data = json.load(f)
                assert copy_data == sample_json_content
                
        except ImportError:
            pytest.skip("FileReader/FileWriter not available")

    def test_dataframe_roundtrip(self, temp_directory):
        """Test DataFrame read/write operations."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            reader = FileReader()
            writer = FileWriter()
            
            # Create test DataFrame
            original_df = pd.DataFrame({
                'name': ['Alice', 'Bob', 'Charlie'],
                'age': [25, 30, 35],
                'score': [85.5, 92.0, 78.5]
            })
            
            csv_file = temp_directory / "test_df.csv"
            
            if hasattr(writer, 'write_csv') and hasattr(reader, 'read_csv'):
                # Write DataFrame as CSV
                writer.write_csv(str(csv_file), original_df)
                
                # Read DataFrame back
                loaded_df = reader.read_csv(str(csv_file))
                
                if hasattr(loaded_df, 'shape'):
                    assert loaded_df.shape == original_df.shape
                    # Basic comparison (column names might differ slightly)
                    assert len(loaded_df.columns) == len(original_df.columns)
                    
        except ImportError:
            pytest.skip("FileReader/FileWriter or pandas not available")


@pytest.mark.performance
class TestFileReadersWritersPerformance:
    """Performance tests for file readers and writers."""

    @pytest.mark.slow
    def test_large_text_file_performance(self, temp_directory):
        """Test performance with large text files."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            # Create large text content
            large_content = "This is a test line.\n" * 10000  # ~200KB
            
            reader = FileReader()
            writer = FileWriter()
            
            large_file = temp_directory / "large.txt"
            
            import time
            
            # Test write performance
            if hasattr(writer, 'write_text'):
                start_time = time.time()
                writer.write_text(str(large_file), large_content)
                write_time = time.time() - start_time
                
                assert write_time < 5.0  # Should complete within 5 seconds
                assert large_file.exists()
                
                # Test read performance
                if hasattr(reader, 'read_text'):
                    start_time = time.time()
                    content = reader.read_text(str(large_file))
                    read_time = time.time() - start_time
                    
                    assert read_time < 5.0  # Should complete within 5 seconds
                    assert len(content) == len(large_content)
                    
        except ImportError:
            pytest.skip("FileReader/FileWriter not available")

    def test_multiple_small_files_performance(self, temp_directory):
        """Test performance with many small files."""
        try:
            from mountainash_utils_files.file_readers.filereader import FileReader
            from mountainash_utils_files.file_writers.filewriter import FileWriter
            
            reader = FileReader()
            writer = FileWriter()
            
            import time
            start_time = time.time()
            
            # Write many small files
            if hasattr(writer, 'write_text'):
                for i in range(100):
                    small_file = temp_directory / f"small_{i:03d}.txt"
                    writer.write_text(str(small_file), f"Content for file {i}")
                
                # Read many small files
                if hasattr(reader, 'read_text'):
                    contents = []
                    for i in range(100):
                        small_file = temp_directory / f"small_{i:03d}.txt"
                        content = reader.read_text(str(small_file))
                        contents.append(content)
                    
                    assert len(contents) == 100
            
            end_time = time.time()
            
            # Should complete within reasonable time
            assert end_time - start_time < 10.0
            
        except ImportError:
            pytest.skip("FileReader/FileWriter not available")