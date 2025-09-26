# prepare_and_generate_mysql.py
import base64
import subprocess
import os
import argparse

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Encode file in base64, insert into MySQL, and reconstruct the file.")
    parser.add_argument("--input", "-i", required=True, help="Full path of the file to upload (e.g. php.zip)")
    parser.add_argument("--output-dir", "-o", required=True, help="Directory where the file will be reconstructed")
    parser.add_argument("--host", default="127.0.0.1", help="MySQL host (default: 127.0.0.1)")
    parser.add_argument("--user", "-u", required=True, help="MySQL username")
    parser.add_argument("--password", "-p", required=True, help="MySQL password")
    parser.add_argument("--db", "-d", required=True, help="MySQL database name")
    parser.add_argument(
        "--chunk-size", 
        type=int, 
        default=60, 
        help="Chunk size in KB (default: 60 KB)"
    )
    return parser.parse_args()

def encode_file_to_base64(input_file: str) -> str:
    """Read a binary file, encode it in base64 and return the encoded string"""
    with open(input_file, "rb") as f:
        encoded_data = base64.b64encode(f.read()).decode('utf-8')
    print(f"✅ {input_file} encoded in base64")
    return encoded_data

def split_base64_string(base64_str: str, chunk_size: int) -> list:
    """Split a base64 string into smaller chunks of size chunk_size"""
    parts = [base64_str[i:i+chunk_size] for i in range(0, len(base64_str), chunk_size)]
    print(f"✅ Base64 string split into {len(parts)} parts")
    return parts

def generate_mysql_commands(file_id: str, parts: list, host: str, user: str, password: str, db: str) -> None:
    """Insert all chunks into MySQL using the mysql CLI tool"""
    for index, part in enumerate(parts):
        cmd = [
            "mysql",
            "-h", host,
            "-u", user,
            f"-p{password}",
            "-Bse",
            f"USE {db}; INSERT INTO file_chunks (file_id, chunk_index, data) VALUES ('{file_id}', {index}, '{part}');"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Chunk {index} inserted successfully")
        else:
            print(f"❌ Error inserting chunk {index}: {result.stderr}")
    print("✅ All chunks processed")

def reconstruct_file_mysql(file_name: str, output_dir: str, host: str, user: str, password: str, db: str) -> None:
    """Reconstruct the original file from base64 chunks stored in MySQL"""
    output_path = os.path.join(output_dir, file_name)
    
    # SQL query: concatenate all chunks in order, decode from base64 and write to a file
    query = (
        f"USE {db}; "
        f"SET SESSION group_concat_max_len = 4294967295; "
        f"SELECT FROM_BASE64(GROUP_CONCAT(data ORDER BY chunk_index SEPARATOR '')) "
        f"INTO DUMPFILE '{output_path}' "
        f"FROM file_chunks WHERE file_id = '{file_name}';"
    )

    # Execute query with mysql client
    cmd = [
        "mysql",
        "-h", host,
        "-u", user,
        f"-p{password}",
        "-Bse",
        query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ File {file_name} successfully reconstructed in {output_path}")
    else:
        print(f"❌ Error reconstructing file: {result.stderr}")

if __name__ == "__main__":
    args = parse_args()

    # Validate input file
    if not os.path.isfile(args.input):
        print(f"❌ File not found: {args.input}")
        exit(1)

    base_name = os.path.basename(args.input)
    chunk_size_bytes = args.chunk_size * 1024  # Convert KB → bytes

    # Step 1: Encode file in base64
    encoded = encode_file_to_base64(args.input)

    # Step 2: Split into parts
    parts = split_base64_string(encoded, chunk_size_bytes)

    # Step 3: Insert parts into MySQL
    generate_mysql_commands(base_name, parts, args.host, args.user, args.password, args.db)

    # Step 4: Reconstruct original file from MySQL
    reconstruct_file_mysql(base_name, args.output_dir, args.host, args.user, args.password, args.db)

    # Clean Server
    print(f"Run this to clean:\n\nIf you are in production, be careful!\nmysql -h {args.host} -u {args.user} -p\"{args.password}\" -Bse \"USE {args.db}; DELETE FROM file_chunks WHERE file_id = '{base_name}'; SELECT ROW_COUNT();\"")

    # Example
    # python3 upload_with_mysql.py --input "php.zip" --output-dir "C:/ProgramData/MySQL/MySQL Server 8.0/Uploads" --host 192.168.1.163 --user cla --password root --db testdb --chunk-size 60
