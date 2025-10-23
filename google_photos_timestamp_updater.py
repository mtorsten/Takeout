#!/usr/bin/env python3
"""
Google Photos Timestamp Updater

A command-line tool that processes Google Photos export data to update file timestamps
based on metadata. The tool reads supplemental metadata files containing photoTakenTime
information and applies these timestamps to the corresponding media files.
"""

import os
import sys
import json
import logging
import argparse
import tempfile
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class PhotoMetadata:
    """Data class representing photo metadata from Google Photos export."""
    title: str
    photo_taken_time: int  # Unix timestamp
    creation_time: int     # Unix timestamp


@dataclass
class ProcessingResult:
    """Data class for tracking processing results and statistics."""
    total_metadata_files: int
    successful_updates: int
    failed_updates: int
    media_without_metadata: int
    errors: List[str]


@dataclass
class FileProcessingState:
    """Data class for tracking file processing state during execution."""
    metadata_files: List[str]
    media_files: List[str]
    orphaned_media: List[str]  # Media files without metadata
    processing_errors: List[str]


def setup_logging(log_file_path: str) -> None:
    """
    Set up comprehensive logging configuration for both console and file output.
    
    Args:
        log_file_path: Path where the log file should be created
    """
    # Create custom formatter with timestamp, level, and message
    log_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create console handler for INFO level and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler for DEBUG level and above
    try:
        file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
        logging.info(f"Log file created: {log_file_path}")
    except (OSError, IOError) as e:
        logging.error(f"Failed to create log file '{log_file_path}': {e}")
        logging.warning("Continuing with console logging only")


def create_log_filename(base_path: str) -> str:
    """
    Create a timestamped log filename in the specified directory.
    
    Args:
        base_path: Directory where the log file should be created
        
    Returns:
        str: Full path to the log file with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"google_photos_timestamp_updater_{timestamp}.log"
    return os.path.join(base_path, log_filename)


def log_success(message: str) -> None:
    """
    Log a success message at INFO level.
    
    Args:
        message: Success message to log
    """
    logging.info(f"SUCCESS: {message}")


def log_error(message: str) -> None:
    """
    Log an error message at ERROR level.
    
    Args:
        message: Error message to log
    """
    logging.error(f"ERROR: {message}")


def log_warning(message: str) -> None:
    """
    Log a warning message at WARNING level.
    
    Args:
        message: Warning message to log
    """
    logging.warning(f"WARNING: {message}")


def log_progress(current: int, total: int, item_name: str = "items") -> None:
    """
    Log progress information during processing.
    
    Args:
        current: Current number of processed items
        total: Total number of items to process
        item_name: Name of the items being processed (default: "items")
    """
    if total > 0:
        percentage = (current / total) * 100
        logging.info(f"PROGRESS: {current}/{total} {item_name} processed ({percentage:.1f}%)")
    else:
        logging.info(f"PROGRESS: {current} {item_name} processed")


def log_processing_summary(result: ProcessingResult) -> None:
    """
    Log a comprehensive summary of processing results.
    
    Args:
        result: ProcessingResult containing statistics and errors
    """
    logging.info("=" * 60)
    logging.info("PROCESSING SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Total metadata files found: {result.total_metadata_files}")
    logging.info(f"Successful timestamp updates: {result.successful_updates}")
    logging.info(f"Failed timestamp updates: {result.failed_updates}")
    logging.info(f"Media files without metadata: {result.media_without_metadata}")
    
    if result.errors:
        logging.info(f"Total errors encountered: {len(result.errors)}")
        logging.debug("Error details:")
        for error in result.errors:
            logging.debug(f"  - {error}")
    else:
        logging.info("No errors encountered during processing")
    
    success_rate = 0
    if result.total_metadata_files > 0:
        success_rate = (result.successful_updates / result.total_metadata_files) * 100
    
    logging.info(f"Success rate: {success_rate:.1f}%")
    logging.info("=" * 60)


def create_argument_parser():
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='google_photos_timestamp_updater',
        description='Update file timestamps for Google Photos export data based on metadata',
        epilog='This tool recursively processes all .supplemental-metadata.json files '
               'in the specified folder and updates the corresponding media file timestamps '
               'based on the photoTakenTime information.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'folder_path',
        type=str,
        help='Path to the folder containing Google Photos export data. '
             'The tool will recursively process all subdirectories to find '
             '.supplemental-metadata.json files and update corresponding media file timestamps.'
    )
    
    return parser


def validate_path(path: str) -> bool:
    """
    Validate that the provided path exists and is a directory.
    
    Args:
        path: The file system path to validate
        
    Returns:
        bool: True if path exists and is a directory, False otherwise
    """
    if not os.path.exists(path):
        print(f"Error: Path '{path}' does not exist.", file=sys.stderr)
        return False
    
    if not os.path.isdir(path):
        print(f"Error: Path '{path}' is not a directory.", file=sys.stderr)
        return False
    
    return True


def test_read_access(path: str) -> bool:
    """
    Test read access to the specified directory.
    
    Args:
        path: The directory path to test for read access
        
    Returns:
        bool: True if directory is readable, False otherwise
    """
    if not os.access(path, os.R_OK):
        print(f"Error: No read access to directory '{path}'.", file=sys.stderr)
        return False
    
    return True


def test_write_access(path: str) -> bool:
    """
    Test write access to the specified directory by creating a temporary file.
    
    Args:
        path: The directory path to test for write access
        
    Returns:
        bool: True if directory is writable, False otherwise
    """
    try:
        # Create a temporary file in the directory to test write access
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except (OSError, IOError, PermissionError) as e:
        print(f"Error: No write access to directory '{path}': {e}", file=sys.stderr)
        return False


def scan_directory(root_path: str) -> Tuple[List[str], List[str]]:
    """
    Recursively scan directory structure to find metadata and media files.
    
    Args:
        root_path: The root directory path to scan recursively
        
    Returns:
        Tuple[List[str], List[str]]: A tuple containing:
            - List of metadata file paths (.supplemental-metadata.json files)
            - List of all other file paths (potential media files)
    """
    metadata_files = []
    media_files = []
    
    logging.info(f"Starting recursive directory scan of: {root_path}")
    
    try:
        # Use os.walk() to traverse directory structure recursively
        for root, dirs, files in os.walk(root_path):
            logging.debug(f"Scanning directory: {root}")
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file is a metadata file
                if file.endswith(".supplemental-metadata.json"):
                    metadata_files.append(file_path)
                    logging.debug(f"Found metadata file: {file_path}")
                else:
                    # Collect all other files as potential media files
                    media_files.append(file_path)
                    logging.debug(f"Found media file: {file_path}")
        
        logging.info(f"Directory scan completed. Found {len(metadata_files)} metadata files and {len(media_files)} media files")
        
    except (OSError, IOError, PermissionError) as e:
        error_msg = f"Error scanning directory '{root_path}': {e}"
        log_error(error_msg)
        raise RuntimeError(error_msg)
    
    return metadata_files, media_files


def parse_metadata_file(file_path: str) -> Optional[int]:
    """
    Parse JSON metadata file and extract photoTakenTime timestamp.
    
    Args:
        file_path: Path to the .supplemental-metadata.json file
        
    Returns:
        Optional[int]: Unix timestamp from photoTakenTime field, or None if parsing fails
    """
    logging.debug(f"Parsing metadata file: {file_path}")
    
    try:
        # Read and parse JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        logging.debug(f"Successfully loaded JSON from: {file_path}")
        
        # Extract photoTakenTime.timestamp from nested structure
        if 'photoTakenTime' not in metadata:
            log_error(f"Missing 'photoTakenTime' field in metadata file: {file_path}")
            return None
        
        photo_taken_time = metadata['photoTakenTime']
        
        if not isinstance(photo_taken_time, dict):
            log_error(f"Invalid 'photoTakenTime' format (not a dict) in metadata file: {file_path}")
            return None
        
        if 'timestamp' not in photo_taken_time:
            log_error(f"Missing 'timestamp' field in photoTakenTime in metadata file: {file_path}")
            return None
        
        timestamp_str = photo_taken_time['timestamp']
        
        if not isinstance(timestamp_str, str):
            log_error(f"Invalid timestamp format (not a string) in metadata file: {file_path}")
            return None
        
        # Convert timestamp string to integer
        try:
            timestamp = int(timestamp_str)
            logging.debug(f"Extracted timestamp {timestamp} from: {file_path}")
            return timestamp
        except ValueError as e:
            log_error(f"Failed to convert timestamp '{timestamp_str}' to integer in metadata file: {file_path}: {e}")
            return None
    
    except FileNotFoundError:
        log_error(f"Metadata file not found: {file_path}")
        return None
    except PermissionError:
        log_error(f"Permission denied reading metadata file: {file_path}")
        return None
    except json.JSONDecodeError as e:
        log_error(f"Invalid JSON format in metadata file: {file_path}: {e}")
        return None
    except (OSError, IOError) as e:
        log_error(f"Error reading metadata file: {file_path}: {e}")
        return None
    except Exception as e:
        log_error(f"Unexpected error parsing metadata file: {file_path}: {e}")
        return None


def convert_timestamp_for_file_operations(timestamp: int) -> int:
    """
    Convert and validate Unix timestamp for file system operations.
    
    Args:
        timestamp: Unix timestamp as integer
        
    Returns:
        int: Validated timestamp suitable for file operations
        
    Raises:
        ValueError: If timestamp is invalid or out of reasonable range
    """
    logging.debug(f"Converting timestamp for file operations: {timestamp}")
    
    # Validate timestamp is positive
    if timestamp <= 0:
        raise ValueError(f"Invalid timestamp: {timestamp} (must be positive)")
    
    # Validate timestamp is within reasonable range
    # Unix timestamp 0 = January 1, 1970
    # Current time should be reasonable upper bound
    current_time = int(datetime.now().timestamp())
    
    # Allow some future dates (1 year from now) to handle timezone issues
    max_timestamp = current_time + (365 * 24 * 60 * 60)
    
    if timestamp > max_timestamp:
        raise ValueError(f"Timestamp {timestamp} appears to be too far in the future")
    
    # Minimum reasonable timestamp (January 1, 1990)
    min_timestamp = 631152000
    if timestamp < min_timestamp:
        raise ValueError(f"Timestamp {timestamp} appears to be too old (before 1990)")
    
    logging.debug(f"Timestamp {timestamp} validated successfully")
    return timestamp


def get_corresponding_media_file(metadata_path: str) -> str:
    """
    Generate corresponding media file path by removing the metadata suffix.
    
    Args:
        metadata_path: Path to the .supplemental-metadata.json file
        
    Returns:
        str: Path to the corresponding media file
        
    Raises:
        ValueError: If the metadata path doesn't end with the expected suffix
    """
    metadata_suffix = ".supplemental-metadata.json"
    
    logging.debug(f"Resolving media file path for metadata: {metadata_path}")
    
    if not metadata_path.endswith(metadata_suffix):
        raise ValueError(f"Invalid metadata file path: {metadata_path} (must end with {metadata_suffix})")
    
    # Remove the metadata suffix to get the media file path
    media_file_path = metadata_path[:-len(metadata_suffix)]
    
    logging.debug(f"Resolved media file path: {media_file_path}")
    return media_file_path


def verify_media_file_exists(media_file_path: str) -> bool:
    """
    Verify that the corresponding media file exists before processing.
    
    Args:
        media_file_path: Path to the media file to verify
        
    Returns:
        bool: True if media file exists and is accessible, False otherwise
    """
    logging.debug(f"Verifying media file exists: {media_file_path}")
    
    try:
        if not os.path.exists(media_file_path):
            log_warning(f"Media file does not exist: {media_file_path}")
            return False
        
        if not os.path.isfile(media_file_path):
            log_warning(f"Media path is not a file: {media_file_path}")
            return False
        
        # Test read access to the file
        if not os.access(media_file_path, os.R_OK):
            log_warning(f"No read access to media file: {media_file_path}")
            return False
        
        logging.debug(f"Media file verified successfully: {media_file_path}")
        return True
    
    except (OSError, IOError) as e:
        log_warning(f"Error verifying media file {media_file_path}: {e}")
        return False


def detect_orphaned_media_files(metadata_files: List[str], media_files: List[str]) -> List[str]:
    """
    Compare media files against metadata files to identify orphaned media files.
    
    Args:
        metadata_files: List of metadata file paths
        media_files: List of media file paths
        
    Returns:
        List[str]: List of media files that don't have corresponding metadata files
    """
    logging.info("Starting orphaned media file detection")
    
    # Create a set of expected media file paths based on metadata files
    expected_media_files = set()
    
    for metadata_file in metadata_files:
        # Remove the .supplemental-metadata.json suffix to get the corresponding media file path
        if metadata_file.endswith(".supplemental-metadata.json"):
            media_file_path = metadata_file[:-len(".supplemental-metadata.json")]
            expected_media_files.add(media_file_path)
            logging.debug(f"Expected media file from metadata: {media_file_path}")
    
    # Find media files that don't have corresponding metadata
    orphaned_media = []
    media_files_set = set(media_files)
    
    for media_file in media_files:
        if media_file not in expected_media_files:
            orphaned_media.append(media_file)
            logging.debug(f"Orphaned media file found: {media_file}")
    
    # Log orphaned media files
    if orphaned_media:
        logging.info(f"Found {len(orphaned_media)} media files without corresponding metadata:")
        for orphaned_file in orphaned_media:
            log_warning(f"Media file without metadata: {orphaned_file}")
    else:
        logging.info("No orphaned media files found - all media files have corresponding metadata")
    
    logging.info(f"Orphaned media file detection completed. Found {len(orphaned_media)} orphaned files")
    
    return orphaned_media


def update_file_timestamps(file_path: str, timestamp: int) -> bool:
    """
    Update both creation and modification times for a file using the provided timestamp.
    
    Args:
        file_path: Path to the file whose timestamps should be updated
        timestamp: Unix timestamp to set for both creation and modification times
        
    Returns:
        bool: True if timestamp update was successful, False otherwise
    """
    logging.debug(f"Updating timestamps for file: {file_path} with timestamp: {timestamp}")
    
    try:
        # Validate timestamp before using it
        validated_timestamp = convert_timestamp_for_file_operations(timestamp)
        
        # Use os.utime() to update both access time and modification time
        # Setting both atime (access time) and mtime (modification time) to the same value
        os.utime(file_path, (validated_timestamp, validated_timestamp))
        
        # Convert timestamp to readable format for logging
        readable_time = datetime.fromtimestamp(validated_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        log_success(f"Updated timestamps for '{file_path}' to {readable_time}")
        
        logging.debug(f"Successfully updated timestamps for: {file_path}")
        return True
        
    except ValueError as e:
        log_error(f"Invalid timestamp {timestamp} for file '{file_path}': {e}")
        return False
    except FileNotFoundError:
        log_error(f"File not found when updating timestamps: {file_path}")
        return False
    except PermissionError:
        log_error(f"Permission denied when updating timestamps for file: {file_path}")
        return False
    except OSError as e:
        log_error(f"OS error when updating timestamps for file '{file_path}': {e}")
        return False
    except Exception as e:
        log_error(f"Unexpected error updating timestamps for file '{file_path}': {e}")
        return False


def process_single_metadata_file(metadata_file_path: str, processing_result: ProcessingResult) -> bool:
    """
    Process a single metadata file with comprehensive error handling and recovery.
    
    This function handles all aspects of processing one metadata file:
    - Parse the metadata to extract timestamp
    - Find the corresponding media file
    - Update the media file's timestamps
    - Handle all errors gracefully and continue processing
    
    Args:
        metadata_file_path: Path to the metadata file to process
        processing_result: ProcessingResult object to update with statistics
        
    Returns:
        bool: True if processing was successful, False if any error occurred
    """
    logging.debug(f"Processing metadata file: {metadata_file_path}")
    
    try:
        # Parse metadata file to extract timestamp
        timestamp = parse_metadata_file(metadata_file_path)
        if timestamp is None:
            processing_result.failed_updates += 1
            processing_result.errors.append(f"Failed to parse metadata file: {metadata_file_path}")
            return False
        
        # Get corresponding media file path
        try:
            media_file_path = get_corresponding_media_file(metadata_file_path)
        except ValueError as e:
            error_msg = f"Invalid metadata file path '{metadata_file_path}': {e}"
            log_error(error_msg)
            processing_result.failed_updates += 1
            processing_result.errors.append(error_msg)
            return False
        
        # Verify media file exists before attempting to update timestamps
        if not verify_media_file_exists(media_file_path):
            error_msg = f"Media file not found or not accessible: {media_file_path}"
            log_warning(error_msg)
            processing_result.failed_updates += 1
            processing_result.errors.append(error_msg)
            return False
        
        # Update file timestamps
        if update_file_timestamps(media_file_path, timestamp):
            processing_result.successful_updates += 1
            logging.debug(f"Successfully processed: {metadata_file_path} -> {media_file_path}")
            return True
        else:
            processing_result.failed_updates += 1
            error_msg = f"Failed to update timestamps for media file: {media_file_path}"
            processing_result.errors.append(error_msg)
            return False
    
    except Exception as e:
        # Catch any unexpected errors to ensure processing continues
        error_msg = f"Unexpected error processing metadata file '{metadata_file_path}': {e}"
        log_error(error_msg)
        processing_result.failed_updates += 1
        processing_result.errors.append(error_msg)
        return False


def handle_file_system_errors_gracefully(operation_name: str, file_path: str, error: Exception) -> str:
    """
    Handle file system errors gracefully with appropriate logging and error messages.
    
    Args:
        operation_name: Name of the operation that failed (e.g., "reading", "writing", "updating")
        file_path: Path to the file that caused the error
        error: The exception that was raised
        
    Returns:
        str: Formatted error message for logging and reporting
    """
    error_msg = ""
    
    if isinstance(error, PermissionError):
        error_msg = f"Permission denied {operation_name} file: {file_path}"
        log_error(error_msg)
    elif isinstance(error, FileNotFoundError):
        error_msg = f"File not found when {operation_name}: {file_path}"
        log_error(error_msg)
    elif isinstance(error, OSError):
        error_msg = f"OS error {operation_name} file '{file_path}': {error}"
        log_error(error_msg)
    elif isinstance(error, IOError):
        error_msg = f"IO error {operation_name} file '{file_path}': {error}"
        log_error(error_msg)
    else:
        error_msg = f"Unexpected error {operation_name} file '{file_path}': {error}"
        log_error(error_msg)
    
    return error_msg


def process_all_metadata_files(metadata_files: List[str]) -> ProcessingResult:
    """
    Main processing orchestration function that coordinates all components.
    
    This function implements the main processing loop that:
    - Processes each metadata file using process_single_metadata_file function
    - Implements progress tracking and reporting during processing
    - Coordinates all components and maintains processing statistics
    
    Args:
        metadata_files: List of metadata file paths to process
        
    Returns:
        ProcessingResult: Complete processing statistics and error information
    """
    logging.info("Starting main processing orchestration")
    
    # Initialize processing result with total count
    processing_result = ProcessingResult(
        total_metadata_files=len(metadata_files),
        successful_updates=0,
        failed_updates=0,
        media_without_metadata=0,  # Will be set separately
        errors=[]
    )
    
    logging.info(f"Processing {processing_result.total_metadata_files} metadata files")
    
    # Process each metadata file
    for i, metadata_file_path in enumerate(metadata_files, 1):
        logging.debug(f"Processing file {i}/{processing_result.total_metadata_files}: {metadata_file_path}")
        
        # Process single metadata file with comprehensive error handling
        success = process_single_metadata_file(metadata_file_path, processing_result)
        
        # Report progress at regular intervals (every 10 files or for small batches)
        if i % 10 == 0 or i == processing_result.total_metadata_files or processing_result.total_metadata_files <= 20:
            log_progress(i, processing_result.total_metadata_files, "metadata files")
            
            # Also log current success/failure counts
            logging.info(f"Current status: {processing_result.successful_updates} successful, {processing_result.failed_updates} failed")
    
    logging.info("Main processing orchestration completed")
    logging.info(f"Final results: {processing_result.successful_updates} successful, {processing_result.failed_updates} failed updates")
    
    return processing_result


def main():
    """Main entry point for the Google Photos Timestamp Updater."""
    # Parse command-line arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    print("Google Photos Timestamp Updater")
    print(f"Processing folder: {args.folder_path}")
    
    # Validate the provided folder path
    if not validate_path(args.folder_path):
        sys.exit(1)
    
    if not test_read_access(args.folder_path):
        sys.exit(1)
    
    if not test_write_access(args.folder_path):
        sys.exit(1)
    
    print("Path validation successful - folder is accessible for reading and writing.")
    
    # Initialize logging system
    log_file_path = create_log_filename(args.folder_path)
    setup_logging(log_file_path)
    
    logging.info("Google Photos Timestamp Updater started")
    logging.info(f"Processing folder: {args.folder_path}")
    logging.info("Path validation completed successfully")
    
    try:
        # Step 1: Scan directory for metadata and media files
        logging.info("Step 1: Scanning directory structure")
        metadata_files, media_files = scan_directory(args.folder_path)
        
        if not metadata_files:
            logging.warning("No metadata files found in the specified directory")
            print("No .supplemental-metadata.json files found in the specified directory.")
            print("Please ensure you're pointing to a Google Photos export folder.")
            return
        
        # Step 2: Detect orphaned media files (files without metadata)
        logging.info("Step 2: Detecting orphaned media files")
        orphaned_media = detect_orphaned_media_files(metadata_files, media_files)
        
        # Step 3: Process all metadata files using the orchestration function
        logging.info("Step 3: Processing metadata files and updating timestamps")
        processing_result = process_all_metadata_files(metadata_files)
        
        # Update the orphaned media count in the processing result
        processing_result.media_without_metadata = len(orphaned_media)
        
        # Step 4: Display final summary with processing statistics and log file location
        logging.info("Step 4: Generating final summary")
        log_processing_summary(processing_result)
        
        # Display summary to console
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total metadata files processed: {processing_result.total_metadata_files}")
        print(f"Successful timestamp updates: {processing_result.successful_updates}")
        print(f"Failed timestamp updates: {processing_result.failed_updates}")
        print(f"Media files without metadata: {processing_result.media_without_metadata}")
        
        if processing_result.total_metadata_files > 0:
            success_rate = (processing_result.successful_updates / processing_result.total_metadata_files) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        print(f"\nDetailed log file created: {log_file_path}")
        
        if processing_result.errors:
            print(f"\n{len(processing_result.errors)} errors encountered during processing.")
            print("Check the log file for detailed error information.")
        
        print("=" * 60)
        
        # Exit with appropriate code based on results
        if processing_result.failed_updates > 0:
            logging.info("Exiting with code 1 due to processing failures")
            sys.exit(1)
        else:
            logging.info("Processing completed successfully")
            
    except KeyboardInterrupt:
        logging.info("Processing interrupted by user")
        print("\nProcessing interrupted by user.")
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error during processing: {e}"
        log_error(error_msg)
        print(f"Error: {error_msg}")
        print(f"Check the log file for details: {log_file_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()