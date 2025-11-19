from flask import Flask, render_template, request, redirect, url_for
import pyodbc

app = Flask(__name__)

# ✅ SQL SERVER Configuration
db_config = {
    'host': '125.22.69.164',
    'user': 'abhishek',
    'password': 'Noida@123',
    'database': 'Test',
    'port': '1433'
}

# -----------------------------------------
# 🔌 DB Connection (pyodbc)
# -----------------------------------------
def get_connection():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={db_config['host']},{db_config['port']};"
        f"DATABASE={db_config['database']};"
        f"UID={db_config['user']};"
        f"PWD={db_config['password']};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;",
        autocommit=True
    )
    return conn


# -----------------------------------------
# 🏠 Home Page (Session Metrics)
# -----------------------------------------
@app.route('/')
def index():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT TOP 20 * FROM session_metrics ORDER BY id DESC;")
    rows = cursor.fetchall()

    # Convert pyodbc rows → dict
    sessions = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

    cursor.close()
    conn.close()

    return render_template('index.html', sessions=sessions)


# -----------------------------------------
# ➕ Add Instruction
# -----------------------------------------
@app.route('/add', methods=['POST'])
def add_instruction():
    context = request.form.get('context')

    if context.strip():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO instruction (context) VALUES (?)", (context,))
        cursor.close()
        conn.close()

    return redirect(url_for('show_instructions'))


# -----------------------------------------
# 📄 Show Instructions
# -----------------------------------------
@app.route('/instructions')
def show_instructions():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, context FROM instruction ORDER BY id DESC;")
    rows = cursor.fetchall()

    instructions = [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

    cursor.close()
    conn.close()

    return render_template('instructions.html', instructions=instructions)


# -----------------------------------------
# ✏ Edit Instruction
# -----------------------------------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_instruction(id):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        new_context = request.form.get('context')
        cursor.execute("UPDATE instruction SET context = ? WHERE id = ?", (new_context, id))
        cursor.close()
        conn.close()
        return redirect(url_for('show_instructions'))

    cursor.execute("SELECT * FROM instruction WHERE id = ?", (id,))
    row = cursor.fetchone()
    instruction = dict(zip([col[0] for col in cursor.description], row))

    cursor.close()
    conn.close()

    return render_template('edit.html', instruction=instruction)


# -----------------------------------------
# ❌ Delete Instruction
# -----------------------------------------
@app.route('/delete/<int:id>')
def delete_instruction(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM instruction WHERE id = ?", (id,))

    cursor.close()
    conn.close()

    return redirect(url_for('show_instructions'))


# -----------------------------------------
# 🎤 Transcripts Viewer (Search + Filter)
# -----------------------------------------
@app.route('/transcripts')
def transcripts():
    search = request.args.get('search', '').strip()
    speaker = request.args.get('speaker', '')
    session_id = request.args.get('session_id', '')

    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM transcripts WHERE 1=1"
    params = []

    if search:
        query += " AND [user] LIKE ?"
        params.append(f"%{search}%")

    if speaker:
        query += " AND agent LIKE ?"
        params.append(f"%{speaker}%")

    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)

    # 🔥 sorting oldest → newest
    query += " ORDER BY datetime ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    transcripts = [
        dict(zip([col[0] for col in cursor.description], row))
    for row in rows]

    cursor.close()
    conn.close()

    return render_template('transcripts.html', transcripts=transcripts)


# -----------------------------------------
# RUN SERVER
# -----------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
