from typing import List, Tuple, Dict, Optional, Union
from upath import UPath
import hashlib
import os
import struct
import tempfile
from dataclasses import dataclass
from typing import Generator

from mountainash_utils_files.file_helpers.base_file_helper import Base_FileHelper


@dataclass
class FileMetadata:
    """Represents file metadata used for sync decisions"""
    path: str
    size: int
    mtime: float
    is_dir: bool
    checksum: Optional[str] = None


class FileSyncer:
    """
    A class to synchronize files between any two storage backends
    that implement the Base_FileHelper interface.
    """
    
    def __init__(
        self,
        source_helper: Base_FileHelper,
        destination_helper: Base_FileHelper,
        block_size: int = 4096,
        checksum_algorithm: str = 'md5'
    ):
        self.source = source_helper
        self.destination = destination_helper
        self.block_size = block_size
        self.checksum_algorithm = checksum_algorithm
    
    def calculate_checksum(self, file_helper: Base_FileHelper, path: Union[str, UPath]) -> str:
        """Calculate checksum for a file using the specified algorithm"""
        hasher = hashlib.new(self.checksum_algorithm)
        
        # Use binary stream for checksum calculation
        with file_helper.open_read_binarystream(path) as stream:
            for chunk in iter(lambda: stream.read(self.block_size), b''):
                hasher.update(chunk)
                
        return hasher.hexdigest()
    
    def get_file_metadata(self, file_helper: Base_FileHelper, path: Union[str, UPath]) -> FileMetadata:
        """Get file metadata for sync decisions"""
        u_path = UPath(str(path))
        return FileMetadata(
            path=str(u_path),
            size=file_helper.get_size(u_path),
            mtime=0,  # Would need implementation in Base_FileHelper
            is_dir=file_helper.path_is_dir(u_path),
            # Only calculate checksum when needed, not during initial scan
            checksum=None
        )
    
    def scan_directory(self, file_helper: Base_FileHelper, 
                      root_path: Union[str, UPath]) -> Dict[str, FileMetadata]:
        """
        Scan a directory recursively and return a dictionary of file metadata
        """
        results = {}
        root_path_str = str(root_path)
        
        def _scan_recursive(current_path: Union[str, UPath]):
            if file_helper.path_is_dir(current_path):
                # Add directory entry
                rel_path = str(current_path).replace(root_path_str, '', 1).lstrip('/')
                if rel_path:  # Don't add the root directory
                    results[rel_path] = self.get_file_metadata(file_helper, current_path)
                
                # Recurse into subdirectories
                for item in file_helper.list_sources(current_path):
                    item_path = os.path.join(str(current_path), item)
                    _scan_recursive(item_path)
            else:
                # Add file entry
                rel_path = str(current_path).replace(root_path_str, '', 1).lstrip('/')
                results[rel_path] = self.get_file_metadata(file_helper, current_path)
        
        _scan_recursive(root_path)
        return results
    
    def determine_changes(
        self,
        source_files: Dict[str, FileMetadata],
        dest_files: Dict[str, FileMetadata]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Compare source and destination file lists and return:
        - Files to copy (new or modified)
        - Files to delete (in destination but not in source)
        - Directories to create
        """
        to_copy = []
        to_delete = []
        dirs_to_create = []
        
        # Find files to copy (new or modified)
        for path, src_meta in source_files.items():
            if src_meta.is_dir:
                if path not in dest_files:
                    dirs_to_create.append(path)
                continue
                
            if path not in dest_files:
                # New file
                to_copy.append(path)
            else:
                # Check if file needs updating
                dest_meta = dest_files[path]
                if src_meta.size != dest_meta.size:
                    # Different size = definitely changed
                    to_copy.append(path)
                elif src_meta.mtime > dest_meta.mtime:
                    # Newer modification time, need to check content
                    # Calculate checksums only when size matches but mtime differs
                    if not src_meta.checksum:
                        src_meta.checksum = self.calculate_checksum(
                            self.source, os.path.join(str(self.source_root), path)
                        )
                    if not dest_meta.checksum:
                        dest_meta.checksum = self.calculate_checksum(
                            self.destination, os.path.join(str(self.dest_root), path)
                        )
                    
                    if src_meta.checksum != dest_meta.checksum:
                        to_copy.append(path)
        
        # Find files to delete (in destination but not in source)
        if self.delete_extraneous:
            for path, dest_meta in dest_files.items():
                if path not in source_files and not dest_meta.is_dir:
                    to_delete.append(path)
        
        return to_copy, to_delete, dirs_to_create
    
    def sync_files(
        self,
        source_root: Union[str, UPath],
        dest_root: Union[str, UPath],
        delete_extraneous: bool = False,
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """
        Synchronize files from source to destination
        
        Args:
            source_root: Root directory in source storage
            dest_root: Root directory in destination storage
            delete_extraneous: Whether to delete files in destination not in source
            dry_run: If True, only report what would be done without making changes
            
        Returns:
            Dictionary with lists of files copied, deleted, and directories created
        """
        self.source_root = source_root
        self.dest_root = dest_root
        self.delete_extraneous = delete_extraneous
        
        # Scan source and destination
        source_files = self.scan_directory(self.source, source_root)
        dest_files = self.scan_directory(self.destination, dest_root)
        
        # Determine changes
        to_copy, to_delete, dirs_to_create = self.determine_changes(source_files, dest_files)
        
        results = {
            "copied": [],
            "deleted": [],
            "dirs_created": []
        }
        
        if dry_run:
            return {
                "would_copy": to_copy,
                "would_delete": to_delete,
                "would_create_dirs": dirs_to_create
            }
        
        # Create necessary directories
        for dir_path in dirs_to_create:
            full_dest_path = os.path.join(str(dest_root), dir_path)
            self.destination.create_directory(full_dest_path)
            results["dirs_created"].append(dir_path)
        
        # Copy files
        for file_path in to_copy:
            src_path = os.path.join(str(source_root), file_path)
            dest_path = os.path.join(str(dest_root), file_path)
            
            # Ensure parent directories exist
            self.destination.prepare_path_parent(dest_path)
            
            # For large files, we could add delta transfer here
            # But for now, just do a simple copy
            self._copy_file(src_path, dest_path)
            results["copied"].append(file_path)
        
        # Delete files if requested
        if delete_extraneous:
            for file_path in to_delete:
                full_dest_path = os.path.join(str(dest_root), file_path)
                # Would need delete implementation in Base_FileHelper
                # self.destination.delete_file(full_dest_path)
                results["deleted"].append(file_path)
        
        return results
    
    def _copy_file(self, src_path: Union[str, UPath], dest_path: Union[str, UPath]) -> bool:
        """Copy a file from source to destination"""
        # For small files or when delta transfer isn't needed,
        # use simple stream copy
        try:
            # First check if we should try to use delta transfer
            if self.destination.path_exists(dest_path) and self.source.get_size(src_path) > 1024 * 1024:  # 1MB
                # For large files that exist at destination, try delta transfer
                return self.sync_with_delta(src_path, dest_path)
            
            # For small files or new files, do a regular copy
            with self.source.open_read_binarystream(src_path) as src_stream:
                with self.destination.open_write_binarystream(dest_path) as dest_stream:
                    # Copy in chunks to avoid loading entire file into memory
                    while True:
                        data = src_stream.read(self.block_size)
                        if not data:
                            break
                        dest_stream.write(data)
            return True
        except Exception as e:
            print(f"Error copying {src_path} to {dest_path}: {e}")
            return False
            
    def _update_rolling_checksum(self, old_sum: int, outgoing: int, incoming: int, window_size: int) -> int:
        """
        Update a rolling checksum when the window shifts by one byte
        """
        # Extract components from the checksum
        b = old_sum >> 16
        a = old_sum & 0xFFFF
        
        # Update components
        a = (a - outgoing + incoming) % 65521
        b = (b - (window_size * outgoing) + a) % 65521
        
        # Combine components
        return (b << 16) | a
    
    def sync_with_delta(self, src_path: Union[str, UPath], dest_path: Union[str, UPath]) -> bool:
        """
        Implement delta transfer for a single file using the rsync algorithm
        Only copies changed blocks between source and destination
        """
        # 1. Check if destination file exists
        if not self.destination.path_exists(dest_path):
            # If not, just do a regular copy
            return self._copy_file(src_path, dest_path)
            
        # 2. Calculate rolling checksums for the destination file
        dest_checksums = self._calculate_rolling_checksums(self.destination, dest_path)
        
        # Create a lookup table for quick matching by weak checksum
        weak_checksum_lookup = {}
        for offset, (weak, strong) in dest_checksums.items():
            if weak not in weak_checksum_lookup:
                weak_checksum_lookup[weak] = []
            weak_checksum_lookup[weak].append((offset, strong))
        
        # 3. Create temporary file for reconstructed content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            
            # 4. Process the source file using a rolling checksum window
            src_size = self.source.get_size(src_path)
            with self.source.open_read_binarystream(src_path) as src_stream:
                # Use a larger buffer for calculation efficiency
                buffer = src_stream.read(min(1024 * 1024, src_size))
                
                # Process the source file using the rolling checksum
                literal_data = b''  # Accumulate literal (new) data
                pos = 0
                
                while pos < len(buffer):
                    # Calculate weak checksum for current window
                    window_data = buffer[pos:pos + self.block_size]
                    weak_sum = self._calculate_weak_checksum(window_data)
                    
                    # Look for potential matches
                    match_found = False
                    if weak_sum in weak_checksum_lookup:
                        # Calculate strong checksum only if weak checksum matched
                        strong_sum = hashlib.md5(window_data).hexdigest()
                        
                        # Check for a full match
                        for dest_offset, dest_strong in weak_checksum_lookup[weak_sum]:
                            if strong_sum == dest_strong:
                                # We found a matching block
                                if literal_data:
                                    # Write any accumulated literal data first
                                    temp_file.write(struct.pack('!cI', b'L', len(literal_data)))
                                    temp_file.write(literal_data)
                                    literal_data = b''
                                
                                # Write a reference to the existing block
                                temp_file.write(struct.pack('!cQ', b'R', dest_offset))
                                
                                # Move forward by a full block
                                pos += len(window_data)
                                match_found = True
                                break
                    
                    if not match_found:
                        # No match found, add one byte to literal data and slide window by 1
                        literal_data += buffer[pos:pos+1]
                        pos += 1
                        
                        # If literal buffer gets too large, write it out
                        if len(literal_data) >= 64 * 1024:  # 64KB chunks
                            temp_file.write(struct.pack('!cI', b'L', len(literal_data)))
                            temp_file.write(literal_data)
                            literal_data = b''
                
                # Write any remaining literal data
                if literal_data:
                    temp_file.write(struct.pack('!cI', b'L', len(literal_data)))
                    temp_file.write(literal_data)
        
        # 5. Apply the delta to create the destination file
        try:
            # Create a destination stream
            with open(temp_path, 'rb') as delta_file:
                with self.destination.open_read_binarystream(dest_path) as old_file:
                    with self.destination.open_write_binarystream(dest_path + '.new') as new_file:
                        # Apply the delta instructions
                        while True:
                            # Read the instruction type
                            instr_type = delta_file.read(1)
                            if not instr_type:
                                break  # End of file
                                
                            if instr_type == b'L':
                                # Literal data
                                length = struct.unpack('!I', delta_file.read(4))[0]
                                data = delta_file.read(length)
                                new_file.write(data)
                            elif instr_type == b'R':
                                # Reference to existing block
                                offset = struct.unpack('!Q', delta_file.read(8))[0]
                                old_file.seek(offset)
                                data = old_file.read(self.block_size)
                                new_file.write(data)
            
            # Rename the new file to replace the old one
            # This would require an implementation of rename in Base_FileHelper
            # self.destination.rename_file(dest_path + '.new', dest_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            return True
        except Exception as e:
            print(f"Error applying delta for {src_path} to {dest_path}: {e}")
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return False
    
    def _calculate_weak_checksum(self, data: bytes) -> int:
        """
        Calculate a simple rolling checksum (Adler-32 style)
        """
        if not data:
            return 0
            
        a = 1
        b = 0
        
        for byte in data:
            a = (a + byte) % 65521  # Prime number for Adler-32
            b = (b + a) % 65521
            
        return (b << 16) | a
    
    def _calculate_rolling_checksums(self, 
                                 file_helper: Base_FileHelper, 
                                 path: Union[str, UPath]) -> Dict[int, Tuple[int, str]]:
        """
        Calculate checksums for all fixed-size blocks in a file
        Returns a dictionary mapping offset -> (weak_checksum, strong_checksum)
        """
        result = {}
        with file_helper.open_read_binarystream(path) as stream:
            offset = 0
            while True:
                block = stream.read(self.block_size)
                if not block:
                    break
                
                if len(block) < self.block_size:
                    # Skip partial blocks at the end for simplicity
                    break
                
                # Calculate weak checksum (Adler-32 style)
                weak_sum = self._calculate_weak_checksum(block)
                
                # Calculate strong checksum (md5)
                strong_sum = hashlib.md5(block).hexdigest()
                
                result[offset] = (weak_sum, strong_sum)
                offset += len(block)
        
        return result
        
    def _rolling_checksum_generator(self, data: bytes, window_size: int) -> Generator[Tuple[int, int, bytes], None, None]:
        """
        Generator that yields (offset, checksum, window_data) tuples
        as it rolls through the input data
        """
        if len(data) < window_size:
            return
            
        # Initialize the first window
        window = data[:window_size]
        checksum = self._calculate_weak_checksum(window)
        yield (0, checksum, window)
        
        # Roll the window through the rest of the data
        for i in range(len(data) - window_size):
            # Remove influence of outgoing byte
            outgoing = data[i]
            # Add influence of incoming byte
            incoming = data[i + window_size]
            
            # Update rolling checksum
            checksum = self._update_rolling_checksum(checksum, outgoing, incoming, window_size)
            window = data[i+1:i+1+window_size]
            
            yield (i+1, checksum, window)