# Design Document

## Overview

The Google Photos Timestamp Updater is a Python command-line tool that processes Google Photos export data to synchronize file timestamps with the actual photo-taken times stored in metadata files. The tool uses a recursive file scanning approach with comprehensive logging and error handling.

## Architecture

The application follows a modular design with clear separation of concerns:

```
google_photos_timestamp_updater.py
├── ArgumentParser (CLI interface)
├── FileScanner (recursive directory traversal)
├── MetadataProcessor (JSON parsing and timestamp extraction)
├── TimestampUpdater (file system timestamp modification)
└── Logger (comprehensive logging system)
```

## Components and Interfaces

### 1. Main Application Controller
- **Purpose**: Orchestrates the entire process flow
- **Responsibilities**: 
  - Parse command-line arguments
  - Initialize logging system
  - Coordinate between components
  - Provide progress reporting and final summary

### 2. Path Validator
- **Purpose**: Validates and tests the provided folder path
- **Interface**:
  ```python
  def validate_path(path: str) -> bool
  def test_read_access(path: str) -> bool
  def test_write_access(path: str) -> bool
  ```
- **Responsibilities**:
  - Verify path exists and is a directory
  - Test read permissions for scanning files
  - Test write permissions for timestamp modification

### 3. File Scanner
- **Purpose**: Recursively discovers metadata and media files
- **Interface**:
  ```python
  def scan_directory(root_path: str) -> Tuple[List[str], List[str]]
  ```
- **Responsibilities**:
  - Recursively traverse directory structure
  - Identify all `.supplemental-metadata.json` files
  - Identify all media files without corresponding metadata
  - Return separate lists for processing and logging

### 4. Metadata Processor
- **Purpose**: Handles JSON parsing and timestamp extraction
- **Interface**:
  ```python
  def parse_metadata_file(file_path: str) -> Optional[int]
  def get_corresponding_media_file(metadata_path: str) -> str
  ```
- **Responsibilities**:
  - Parse JSON metadata files safely
  - Extract photoTakenTime timestamp
  - Convert timestamp format for file system operations
  - Handle malformed or missing data gracefully

### 5. Timestamp Updater
- **Purpose**: Modifies file system timestamps
- **Interface**:
  ```python
  def update_file_timestamps(file_path: str, timestamp: int) -> bool
  ```
- **Responsibilities**:
  - Update both creation and modification times
  - Handle platform-specific timestamp operations
  - Manage file system permission errors
  - Return success/failure status

### 6. Logging System
- **Purpose**: Comprehensive operation and error logging
- **Interface**:
  ```python
  def setup_logging(log_file: str) -> None
  def log_success(message: str) -> None
  def log_error(message: str) -> None
  def log_warning(message: str) -> None
  ```
- **Responsibilities**:
  - Create timestamped log file
  - Log all operations with appropriate levels
  - Track files without metadata
  - Record access denied errors
  - Provide processing statistics

## Data Models

### Metadata File Structure
```python
@dataclass
class PhotoMetadata:
    title: str
    photo_taken_time: int  # Unix timestamp
    creation_time: int     # Unix timestamp
    
@dataclass
class ProcessingResult:
    total_metadata_files: int
    successful_updates: int
    failed_updates: int
    media_without_metadata: int
    errors: List[str]
```

### File Processing State
```python
@dataclass
class FileProcessingState:
    metadata_files: List[str]
    media_files: List[str]
    orphaned_media: List[str]  # Media files without metadata
    processing_errors: List[str]
```

## Error Handling

### Error Categories and Responses

1. **Command Line Errors**:
   - Missing folder parameter → Exit with usage message
   - Invalid folder path → Exit with error message
   - Access permission issues → Exit with permission error

2. **File System Errors**:
   - Metadata file read errors → Log error, continue processing
   - Media file not found → Log warning, continue processing
   - Timestamp update failures → Log error, continue processing
   - Permission denied → Log error, continue processing

3. **Data Processing Errors**:
   - Invalid JSON format → Log error, skip file
   - Missing photoTakenTime field → Log error, skip file
   - Invalid timestamp format → Log error, skip file

### Error Recovery Strategy
- Continue processing remaining files when individual files fail
- Maintain detailed error logs for post-processing review
- Provide comprehensive summary of successes and failures

## Testing Strategy

### Unit Testing Approach
- **Path Validation**: Test with valid/invalid paths, permission scenarios
- **Metadata Processing**: Test with various JSON structures, missing fields
- **Timestamp Operations**: Test timestamp conversion and file system updates
- **Logging System**: Verify log file creation and message formatting

### Integration Testing
- **End-to-End Processing**: Test with sample Google Photos export structure
- **Error Scenarios**: Test behavior with corrupted files, permission issues
- **Large Dataset Handling**: Test performance with substantial file collections

### Test Data Requirements
- Sample metadata files with various timestamp formats
- Test directory structure mimicking Google Photos export
- Files with different permission settings
- Corrupted/malformed JSON files for error testing

## Platform Considerations

### Cross-Platform Compatibility
- Use `os.utime()` for timestamp modification (cross-platform)
- Handle Windows vs Unix path separators appropriately
- Account for different file system timestamp precision
- Consider platform-specific permission models

### Performance Optimization
- Process files in batches to manage memory usage
- Use efficient directory traversal methods
- Implement progress reporting for large datasets
- Consider parallel processing for large file collections (future enhancement)

## Logging and Monitoring

### Log File Structure
```
[TIMESTAMP] [LEVEL] [COMPONENT] Message
2024-10-23 10:30:15 INFO SCANNER Found 1,234 metadata files
2024-10-23 10:30:16 SUCCESS UPDATER Updated timestamp for photo.jpg
2024-10-23 10:30:17 WARNING PROCESSOR Media file missing for metadata.json
2024-10-23 10:30:18 ERROR UPDATER Permission denied updating video.mp4
```

### Progress Reporting
- Display current file being processed
- Show percentage completion
- Report running totals of successes/failures
- Estimate remaining processing time for large datasets