from flask import Flask, request, jsonify, send_from_directory
import mysql.connector
import os
from datetime import datetime
import json
import google.generativeai as genai

# Set your Gemini API key (store securely in real app)
genai.configure(api_key="AIzaSyDohbqd22y_mNFaAEHQ0gnKkn8NJUuNi2g")


app = Flask(__name__)

# MySQL Connection
def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="user"
    )
    print("Connected to MySQL database!")
    return conn

# Serve static files from 'public' directory
# Set up static file serving - this needs to be properly configured
app.static_folder = 'public'

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/login.html')
def login_page():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/signup.html')
def signup_page():
    return send_from_directory(app.static_folder, 'signup.html')

@app.route('/dashboard.html')
def dashboard_page():
    return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/questionnaire.html')
def questionnaire_page():
    return send_from_directory(app.static_folder, 'questionnaire.html')

# Serve any static file from public directory
@app.route('/<path:path>')
def serve_static(path):
    try:
        return send_from_directory(app.static_folder, path)
    except Exception as e:
        print(f"Static file error: {e}")
        return f"File not found: {path}", 404

@app.route('/login', methods=['POST'])
def login():
    # Handle both form data and JSON
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    email = data.get('email')
    password = data.get('password')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = "SELECT * FROM std_login WHERE email = %s AND password = %s"
        cursor.execute(sql, (email, password))
        result = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if result:
            user = result[0]
            return jsonify({
                'success': True,
                'redirectTo': '/dashboard.html',
                'parentEmail': user['email'],
                'parentName': user['username']
            })
        else:
            return jsonify({'success': False, 'error': 'Incorrect Email and/or Password!'}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': 'Server error occurred'}), 500

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm-password')
    
    if password != confirm_password:
        return "Passwords do not match!"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "INSERT INTO std_login (username, email, password) VALUES (%s, %s, %s)"
    cursor.execute(sql, (username, email, password))
    inserted_id = cursor.lastrowid
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return f"User registered successfully with ID: {inserted_id}"

@app.route('/submit-questionnaire', methods=['POST'])
def submit_questionnaire():
    data = request.form
    child_id = data.get('childId')
    parent_email = data.get('parent_email')
    month = data.get('month')
    
    if not child_id or not parent_email or not month:
        return "Missing childId, parent_email, or month.", 400
    
    total_questions = 5
    question_columns = []
    answers = []
    yes_count = 0
    
    for i in range(1, total_questions + 1):
        q_key = f'q{i}'
        answer = data.get(q_key, '').lower() if data.get(q_key) else None
        question_columns.append(q_key)
        answers.append(answer)
        if answer == 'yes':
            yes_count += 1
    
    autism_score = 0 if total_questions == 0 else round((yes_count / total_questions) * 10, 2)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ', '.join(['%s'] * (len(question_columns) + 4))  # +4 for child_id, parent_email, month, autism_score
    columns = ', '.join(['child_id', 'parent_email', 'month'] + question_columns + ['autism_score'])
    
    sql = f"INSERT INTO questionnaire_responses ({columns}) VALUES ({placeholders})"
    values = [child_id, parent_email, month] + answers + [autism_score]
    
    try:
        cursor.execute(sql, values)
        conn.commit()
        cursor.close()
        conn.close()
        return f"<h2>Thank you! Your Month {month} responses have been saved successfully.<br>Autism Score: {autism_score}</h2>"
    except Exception as e:
        print("Error saving responses:", e)
        cursor.close()
        conn.close()
        return "Something went wrong!", 500

@app.route('/get-children', methods=['GET'])
def get_children():
    parent_email = request.args.get('parentEmail')
    if not parent_email:
        return jsonify({"error": "Parent email required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT * FROM children WHERE parent_email = %s"
    cursor.execute(sql, (parent_email,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({"children": results})

@app.route('/add-children', methods=['POST'])
def add_children():
    data = request.json
    parent_email = data.get('parentEmail')
    children = data.get('children')
    
    if not parent_email or not isinstance(children, list) or len(children) == 0:
        return jsonify({"error": "Invalid input data."}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    values = []
    for child in children:
        values.append((parent_email, child['childName'], child['dob']))
    
    sql = "INSERT INTO children (parent_email, child_name, dob) VALUES (%s, %s, %s)"
    
    try:
        affected_rows = 0
        for value in values:
            cursor.execute(sql, value)
            affected_rows += cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "message": "Children added successfully!",
            "inserted": affected_rows
        })
    except Exception as e:
        print("❌ Error inserting children:", e)
        cursor.close()
        conn.close()
        return jsonify({"error": "Error saving children."}), 500

@app.route('/get-progress', methods=['GET'])
def get_progress():
    child_id = request.args.get('childId')
    
    if not child_id:
        return jsonify({"error": "Child ID is required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT DISTINCT month FROM questionnaire_responses WHERE child_id = %s"
    cursor.execute(sql, (child_id,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    submitted_months = [row['month'] for row in results]
    return jsonify({"submittedMonths": submitted_months})

@app.route('/get-answers', methods=['GET'])
def get_answers():
    child_id = request.args.get('childId')
    month = request.args.get('month')
    
    if not child_id or not month:
        return jsonify({"error": "childId and month are required"}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql = """
            SELECT q1, q2, q3, q4, q5 
            FROM questionnaire_responses 
            WHERE child_id = %s AND month = %s
            ORDER BY submitted_at DESC LIMIT 1
        """
        
        cursor.execute(sql, (child_id, month))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Debug output
        print(f"GET /get-answers - childId: {child_id}, month: {month}")
        print(f"Query result: {result}")
        
        # Fix case sensitivity in responses
        if result:
            for key in result:
                if result[key] and isinstance(result[key], str):
                    # Capitalize first letter for Yes/No values
                    if result[key].lower() in ['yes', 'no']:
                        result[key] = result[key].capitalize()
        
        return jsonify({"answers": result})
    except Exception as e:
        print(f"Error in /get-answers: {e}")
        return jsonify({"error": "Server error", "details": str(e)}), 500

@app.route('/get-autism-score', methods=['GET'])
def get_autism_score():
    child_id = request.args.get('childId')
    
    if not child_id:
        return jsonify({"error": "childId is required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT q1, q2, q3, q4, q5 FROM questionnaire_responses WHERE child_id = %s"
    cursor.execute(sql, (child_id,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    yes_count = 0
    total_questions = 0
    
    for row in results:
        for q in ['q1', 'q2', 'q3', 'q4', 'q5']:
            if row[q] is not None:
                total_questions += 1
                if row[q].lower() == 'yes':
                    yes_count += 1
    
    score = 0 if total_questions == 0 else round((yes_count / total_questions) * 10)
    
    return jsonify({"score": score})

@app.route('/get-monthly-scores', methods=['GET'])
def get_monthly_scores():
    child_id = request.args.get('childId')
    
    if not child_id:
        return jsonify({"error": "childId is required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = """
        SELECT month, autism_score
        FROM questionnaire_responses
        WHERE child_id = %s
        ORDER BY month ASC
    """
    
    cursor.execute(sql, (child_id,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    formatted = [{"month": row["month"], "score": row["autism_score"]} for row in results]
    
    return jsonify(formatted)

@app.route('/generate-report', methods=['POST'])
def generate_report():
    data = request.json
    child_id = data.get('childId')
    
    if not child_id:
        return jsonify({"error": "Child ID required"}), 400

    # Fetch autism data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch child's basic information
    cursor.execute("SELECT child_name, dob FROM children WHERE id = %s", (child_id,))
    child_info = cursor.fetchone()

    if not child_info:
        return jsonify({"error": "Child not found"}), 404

    child_name = child_info.get('child_name', "Client")
    date_of_birth = child_info.get('dob', None)
    age = calculate_age(date_of_birth)  # Function to calculate age based on DOB

    # Fetch autism data
    sql = """
        SELECT month, q1, q2, q3, q4, q5, autism_score
        FROM questionnaire_responses
        WHERE child_id = %s
        ORDER BY month ASC
    """
    cursor.execute(sql, (child_id,))
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    if not records:
        return jsonify({"error": "No records found for this child."}), 404

    # Construct input for Gemini
    prompt = f"Generate a psychological report for {child_name}, Age: {age}.\n"
    prompt += f"Date of Birth: {date_of_birth or 'Not Provided'}\n"
    prompt += f"Date of Report: {datetime.now().strftime('%B %d, %Y')}\n"
    prompt += f"Referred By: Parent/Guardian\n"
    prompt += f"Evaluator: AI Generated\n\n"
    prompt += "Based on the autism questionnaire data, provide insights and recommendations.\n"
    prompt += "Assessment Data:\n"

    # Format data into report
    for r in records:
        prompt += f"Month: {r['month']}, Score: {r['autism_score']}, Answers: [{r['q1']}, {r['q2']}, {r['q3']}, {r['q4']}, {r['q5']}]\n"
    
    # Use Gemini Pro model to generate the report
    model = genai.GenerativeModel("models/gemini-2.5-pro-exp-03-25")
    try:
        response = model.generate_content(prompt)
        return jsonify({"report": response.text})
    except Exception as e:
        print("❌ Gemini error:", e)
        return jsonify({"error": "Failed to generate report"}), 500

from datetime import datetime

def calculate_age(dob):
    if not dob:
        return "Not Provided"
    
    # Directly use the datetime.date object without strptime
    today = datetime.today().date()  # Use today's date
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age




# Add error handlers to ensure JSON responses
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {e}")
    return jsonify({"error": "An unexpected error occurred"}), 500

if __name__ == '__main__':
    # Make sure the static folder exists
    if not os.path.exists(app.static_folder):
        os.makedirs(app.static_folder)
        print(f"Created static folder: {app.static_folder}")
    else:
        print(f"Using existing static folder: {app.static_folder}")
    
    print("Starting Flask server on port 3000...")
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)
