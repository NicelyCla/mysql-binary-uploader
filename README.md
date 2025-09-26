# mysql-binary-uploader

This repository contains two Python scripts for uploading large binary files to MySQL using BLOBs and chunking, and reconstructing them on the MySQL server without Base64 encoding.

---

## 1. `mysql_blob_uploader.py`

The main script for uploading and reconstructing large binary files (tested up to 1.7 GB).

### Features
- Uploads binary files in chunks directly into a MySQL table.
- Server-side reconstruction using `INTO DUMPFILE`.
- Option to skip upload and reconstruct an existing file in the DB.
- Uses `LONGBLOB` for efficient storage of large files.

### Example Database and Table Setup
```sql
CREATE DATABASE testdb_blob;
USE testdb_blob;
CREATE TABLE file_chunks (
    file_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    data LONGBLOB NOT NULL,
    PRIMARY KEY(file_id, chunk_index)
);
````

### Usage Examples

**Upload and reconstruct:**

```bash
python3 mysql_blob_uploader.py -i test.zip -u cla -p root -d testdb_blob --host 192.168.1.163 --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"
```

**Reconstruct only (skip upload):**

```bash
python3 mysql_blob_uploader.py --skip-upload --file-id test.zip -u cla -p root -d testdb_blob --host 192.168.1.163 --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"
```

**Alternative shorthand examples from comments:**

```bash
# Only reconstruction
python3 mysql_blob_uploader.py --skip-upload --file-id test.zip --host 192.168.1.163 -u cla -p root -d testdb_blob --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"

# Upload and reconstruction
python3 mysql_blob_uploader.py -i test.zip -o --host 192.168.1.163 -u cla -p root -d testdb_blob --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"
```

---

## 2. `upload_mysql.py`

An alternative script to upload binary files in chunks and reconstruct them on the server using MySQL CLI.

### Features

* Upload files in configurable chunk sizes (default 60 KB).
* Server-side reconstruction using `INTO DUMPFILE`.
* Suitable for environments where `mysql.connector` is unavailable on the client.
* Uses `LONGTEXT` for chunk storage.

### Example Database and Table Setup

```sql
CREATE DATABASE testdb;
USE testdb;
CREATE TABLE file_chunks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    data LONGTEXT NOT NULL,
    UNIQUE KEY (file_id, chunk_index)
);
```

### Usage Example

```bash
python3 upload_with_mysql.py --input "php.zip" --output-dir "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads" --host 192.168.1.163 --user cla --password root --db testdb --chunk-size 60
```

---

## Cleaning Up Chunks

After reconstruction, chunks can be deleted manually:

```bash
mysql -h 127.0.0.1 -u cla -p"root" -Bse "USE testdb_blob; DELETE FROM file_chunks WHERE file_id = 'test.zip'; SELECT ROW_COUNT();"
mysql -h 127.0.0.1 -u cla -p"root" -Bse "USE testdb_blob; OPTIMIZE TABLE file_chunks;"
```

---

**Notes:**

* `mysql_blob_uploader.py` is recommended for very large files (tested up to ~1.7 GB).
* `upload_mysql.py` uses a CLI-based approach, suitable for smaller chunks or limited Python library access on the client.
