import pyodbc

def create_sql_server_connection():
    try:
        connection = pyodbc.connect(
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=125.22.69.164,1433;"
            "DATABASE=Test;"
            "UID=abhishek;"
            "PWD=Noida@123;"
            "Encrypt=no;"                    # disable encryption if certificate not configured
            "TrustServerCertificate=yes;"    # allow untrusted SSL
            "Connection Timeout=15;"         # prevent long hangs
        )

        print("✅ Connected to SQL Server Successfully!")
        return connection

    except Exception as e:
        print(f"❌ SQL Server Connection Error: {e}")
        return None


if __name__ == "__main__":
    conn = create_sql_server_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sys.databases;")
        print(cursor.fetchall())
        conn.close()
def get_connection():
    try:
        connection = pyodbc.connect(
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=125.22.69.164,1433;"
            "DATABASE=Test;"
            "UID=abhishek;"
            "PWD=Noida@123;"
            "Encrypt=no;"                    # disable encryption if certificate not configured
            "TrustServerCertificate=yes;"    # allow untrusted SSL
            "Connection Timeout=15;"         # prevent long hangs
        )

        print("✅ Connected to SQL Server Successfully!")
        return connection
    except Exception as e:
        return None


# -------------------------------------------------------------------
# AUTO TABLE CREATION
# -------------------------------------------------------------------
def init_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Table: instruction
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='instruction' AND xtype='U')
        CREATE TABLE instruction (
            id INT IDENTITY(1,1) PRIMARY KEY,
            context TEXT
        )
    """)

    # Table: session_metrics
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='session_metrics' AND xtype='U')
        CREATE TABLE session_metrics (
            id INT IDENTITY(1,1) PRIMARY KEY,
            session_id VARCHAR(200),
            start_time DATETIME,
            end_time DATETIME,
            llm_tokens INT,
            stt_seconds FLOAT,
            tts_characters INT,
            llm_cost_usd FLOAT,
            stt_cost_usd FLOAT,
            tts_cost_usd FLOAT,
            total_cost_usd FLOAT
        )
    """)

    # Table: transcripts
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='transcripts' AND xtype='U')
        CREATE TABLE transcripts (
            id INT IDENTITY(1,1) PRIMARY KEY,
            session_id VARCHAR(200),
            agent TEXT,
            [user] TEXT,
            datetime DATETIME
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_tables()