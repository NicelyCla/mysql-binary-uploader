import os
import argparse
import mysql.connector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload and reconstruction of large binary files on MySQL using BLOB and chunking"
    )
    parser.add_argument("-i", "--input", help="Path of the file to upload")
    parser.add_argument("--host", default="127.0.0.1", help="MySQL host")
    parser.add_argument("-u", "--user", required=True, help="MySQL username")
    parser.add_argument("-p", "--password", required=True, help="MySQL password")
    parser.add_argument("-d", "--db", required=True, help="MySQL database name")
    parser.add_argument("--chunk-size", type=int, default=1024,
                        help="Chunk size in KB (default 1024)")
    parser.add_argument("--server-dump-path", required=True,
                        help="Path on the MySQL server to save the reconstructed file")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip the upload and only attempt reconstruction")
    parser.add_argument("--file-id", help="File name (required with --skip-upload if --input is missing)")
    args = parser.parse_args()

    if not args.skip_upload and not args.input:
        parser.error("--input is required if not using --skip-upload")

    if args.skip_upload and not args.input and not args.file_id:
        parser.error("--file-id is required if using --skip-upload without --input")

    return args


def connect_db(host, user, password, db):
    return mysql.connector.connect(host=host, user=user, password=password, database=db)


def upload_file(file_path, conn, chunk_size_kb):
    file_id = os.path.basename(file_path)
    chunk_size = chunk_size_kb * 1024
    cursor = conn.cursor()
    index = 0

    # calculate total chunks needed
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + chunk_size - 1) // chunk_size

    f = open(file_path, "rb")
    try:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            cursor.execute(
                "INSERT INTO file_chunks (file_id, chunk_index, data) VALUES (%s, %s, %s)",
                (file_id, index, chunk),
            )
            index += 1
            print(f"\r📦 Uploaded {index}/{total_chunks} chunks", end="", flush=True)

            if index % 10 == 0:
                conn.commit()
        conn.commit()
    finally:
        f.close()
        cursor.close()

    print(f"✅ Upload completed: {index} chunks inserted for {file_id}")
    return file_id


def reconstruct_file_mysql_longblob(file_name, conn, server_dump_path, db):
    """
    Executes on the MySQL server the query:
    SET SESSION group_concat_max_len = 4294967295;
    SELECT GROUP_CONCAT(data ORDER BY chunk_index SEPARATOR '')
      INTO DUMPFILE 'server_dump_path'
      FROM file_chunks WHERE file_id = file_name;
    """
    cursor = conn.cursor()
    try:
        cursor.execute("SET SESSION group_concat_max_len = 4294967295")
        # Consuma eventuali risultati dalla query SET
        cursor.fetchall()

        safe_path = server_dump_path.replace("\\", "\\\\").replace("'", "\\'")
        sql = (
            f"SELECT GROUP_CONCAT(data ORDER BY chunk_index SEPARATOR '') "
            f"INTO DUMPFILE '{safe_path}' "
            f"FROM file_chunks WHERE file_id = %s"
        )

        cursor.execute(sql, (file_name,))
        # Consuma eventuali risultati dalla query INTO DUMPFILE
        try:
            cursor.fetchall()
        except mysql.connector.errors.InterfaceError:
            # INTO DUMPFILE non restituisce risultati, quindi l'errore è normale
            pass
        
        conn.commit()
        print(f"✅ Reconstruction completed successfully: '{file_name}' saved on server at '{server_dump_path}'")

        # Chiudi il cursor corrente prima di crearne uno nuovo
        cursor.close()
        
        # Close the current cursor before creating a new one
        # Create a new cursor for the OPTIMIZE operation
        #cursor = conn.cursor()
        #cursor.execute("DELETE FROM file_chunks WHERE file_id = %s", (file_name,)) #BE CAREFUL ON PRODUCTION
        #cursor.execute("OPTIMIZE TABLE file_chunks")
        # Consume the results of OPTIMIZE TABLE
        #cursor.fetchall()
        #conn.commit()
        #print(f"✅ Chunks for '{file_name}' table optimized")  
      
    finally:
        cursor.close()


if __name__ == "__main__":

    """
    Example of creating DB and table:

    CREATE DATABASE testdb_binary;
    USE testdb_binary;
    CREATE TABLE file_chunks (
        file_id VARCHAR(255) NOT NULL,
        chunk_index INT NOT NULL,
        data LONGBLOB NOT NULL,
        PRIMARY KEY(file_id, chunk_index)
    );
    """

    args = parse_args()

    conn = connect_db(args.host, args.user, args.password, args.db)

    try:
        if args.skip_upload:
            file_id = os.path.basename(args.input) if args.input else args.file_id
        else:
            if not os.path.isfile(args.input):
                print(f"❌ File not found: {args.input}")
                exit(1)
            file_id = upload_file(args.input, conn, args.chunk_size)

        print("\nAttempting reconstruction with DUMPFILE (server-side)...")
        reconstruct_file_mysql_longblob(file_id, conn, args.server_dump_path, args.db)

    finally:
        conn.close()
    print()
    print(f"✅ Done. To clean the table manually:")
    print(f"mysql -h {args.host} -u {args.user} -p\"{args.password}\" -Bse \"USE {args.db}; DELETE FROM file_chunks WHERE file_id = '{file_id}'; SELECT ROW_COUNT();\"")
    print(f"mysql -h {args.host} -u {args.user} -p\"{args.password}\" -Bse \"USE {args.db}; OPTIMIZE TABLE file_chunks;\"")

    #Only reconstruction
    #python3 mysql_blob_uploader.py --skip-upload --file-id test.zip --host 192.168.1.163 -u root -p root -d testdb_binary --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"

    #Upload and reconstruction
    #python3 mysql_blob_uploader.py -i test.zip -o --host 192.168.1.163 -u root -p root -d testdb_binary --server-dump-path "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/zip_restored.zip"

