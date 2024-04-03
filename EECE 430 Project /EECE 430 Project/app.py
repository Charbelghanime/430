import datetime
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure secret key

# Sample data for employees and managers (you can replace this with a database)
conn = sqlite3.connect('employees.db', check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS employees
             (username TEXT PRIMARY KEY, password TEXT, department TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS managers
             (username TEXT PRIMARY KEY, password TEXT, department TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS attendance
             (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, status TEXT, FOREIGN KEY(username) REFERENCES employees(username))''')
c.execute('''CREATE TABLE IF NOT EXISTS tasks
             (task_id INTEGER PRIMARY KEY AUTOINCREMENT,
             employee_username TEXT,
             manager_username TEXT,
             task_name TEXT,
             progress INTEGER,
             FOREIGN KEY (employee_username) REFERENCES employees(username),
             FOREIGN KEY (manager_username) REFERENCES managers(username))''')

c.execute('''CREATE TABLE IF NOT EXISTS availability
             (employee_username TEXT, manager_username TEXT, date DATE, start_time TIME, end_time TIME,
             PRIMARY KEY (employee_username, manager_username, date),
             FOREIGN KEY (employee_username) REFERENCES employees(username),
             FOREIGN KEY (manager_username) REFERENCES managers(username))''')
c.execute('''CREATE TABLE IF NOT EXISTS employee_attendance
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              employee_username TEXT,
              date DATE,
              status TEXT)''')


# Commit the transaction to apply the changes
conn.commit()

c.execute("SELECT * FROM employee_attendance")

# Fetch all rows from the result set
rows = c.fetchall()

# Print the selected records
for row in rows:
    print(row)


attendance_report = []
# Insert manager (if not exists)
c.execute("INSERT OR IGNORE INTO managers VALUES (?, ?, ?)", ('manager1', 'pass1', 'IT'))
conn.commit()



# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        if role == 'employee':
            c.execute("SELECT * FROM employees WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()
            if user:
                session['username'] = username
                return redirect(url_for('employee_dashboard'))
            else:
                return render_template('login.html', error='Invalid employee credentials')

        elif role == 'manager':
            c.execute("SELECT * FROM managers WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()
            if user:
                session['username'] = username
                return redirect(url_for('manager_dashboard'))
            else:
                return render_template('login.html', error='Invalid manager credentials')

    return render_template('login.html')
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' in session:
        if request.method == 'POST':
            old_username = session['username']  # Get the current username from the session
            old_password = request.form['old_password']
            new_password = request.form['new_password']

            # Check if the user exists in either employees or managers table
            c.execute("SELECT * FROM employees WHERE username = ? AND password = ?", (old_username, old_password))
            employee = c.fetchone()
            if not employee:
                c.execute("SELECT * FROM managers WHERE username = ? AND password = ?", (old_username, old_password))
                manager = c.fetchone()

            if employee or manager:
                # Update the password for the user
                if employee:
                    c.execute("UPDATE employees SET password = ? WHERE username = ?", (new_password, old_username))
                else:
                    c.execute("UPDATE managers SET password = ? WHERE username = ?", (new_password, old_username))
                conn.commit()
                return redirect(url_for('login'))
            else:
                error = 'Invalid old password or username.'
                return render_template('change_password.html', error=error)
        else:
            return render_template('change_password.html')
    else:
        return redirect(url_for('login'))



@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/employee_dashboard', methods=['GET', 'POST'])
def employee_dashboard():
    if 'username' in session:
        username = session['username']
        if request.method == 'POST':

            # Handling attendance submission
            status = request.form.get('status')  # Use .get() to avoid KeyError
            manager_username = request.form.get('username')
            today = datetime.now().date()
            if status is not None:  # Check if status field is present in the form
                c.execute("INSERT INTO attendance (employee_username, manager_username, date, status) VALUES (?, ?, ?, ?)",
                          (username, manager_username, today, status))
                conn.commit()

            # Handling task progress update
            task_name = request.form.get('task_name')
            new_progress = int(request.form.get('progress', 0))  # Provide a default value if progress is not present
            if task_name is not None:  # Check if task_name field is present in the form
                c.execute("UPDATE tasks SET progress = ? WHERE employee_username = ? AND task_name = ?",
                          (new_progress, username, task_name))
                conn.commit()

            # Redirect to refresh the page and prevent form resubmission
            return redirect(url_for('employee_dashboard'))

        # Fetch tasks assigned to the current employee from the database
        c.execute("SELECT * FROM tasks WHERE employee_username = ?", (username,))
        tasks = c.fetchall()

        # Fetch scheduled meetings for the current employee from the database
        c.execute("SELECT a.date, a.start_time, a.end_time, e.username AS employee_username, m.username AS manager_username FROM availability a INNER JOIN employees e ON a.employee_username = e.username INNER JOIN managers m ON a.manager_username = m.username WHERE a.employee_username = ? ORDER BY a.date ASC, a.start_time ASC", (username,))
        meetings = c.fetchall()

        return render_template('employee_dashboard.html', tasks=tasks, meetings=meetings)
    else:
        return redirect(url_for('login'))






@app.route('/employee_list', methods=['GET', 'POST'])
def employee_list():
    if 'username' in session:  # Assuming 'username' is the key for the logged-in user in the session
        # Fetch all employees and their tasks for task assignment
        c.execute("SELECT * FROM employees")
        employees = c.fetchall()
        employees_with_tasks = []
        for employee in employees:
            c.execute("SELECT * FROM tasks WHERE employee_username = ?", (employee[0],))
            tasks = c.fetchall()
            employees_with_tasks.append((employee, tasks))

        # Fetch scheduled meetings from the database
        manager_username = session['username']  # Assuming manager's username is stored in session
        c.execute("SELECT a.date, a.start_time, a.end_time, e.username AS employee_username, m.username AS manager_username FROM availability a INNER JOIN employees e ON a.employee_username = e.username INNER JOIN managers m ON a.manager_username = m.username WHERE a.manager_username = ? ORDER BY a.date ASC, a.start_time ASC", (manager_username,))
        scheduled_meetings = c.fetchall()

        return render_template('manager_dashboard.html', employees_with_tasks=employees_with_tasks, scheduled_meetings=scheduled_meetings)
    else:
        return redirect(url_for('login'))  # Redirect to login if not logged in


@app.route('/schedule_meeting', methods=['GET', 'POST'])
def schedule_meeting():
    if 'username' in session:
        if request.method == 'POST':
            manager_username = session['username']
            employee_username = request.form['employee_username']
            meeting_date = request.form['meeting_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']

            if check_availability(employee_username, manager_username, meeting_date, start_time, end_time):
                c.execute("INSERT INTO availability (employee_username, manager_username, date, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                          (employee_username, manager_username, meeting_date, start_time, end_time))
                conn.commit()
                return redirect(url_for('manager_dashboard'))
            else:
                return "Employee or manager is not available at the selected date and time."
        else:
            # Handle GET request (rendering form or other content)
            # For example, you could render a form to schedule a meeting here
            return render_template('schedule_meeting.html')
    else:
        return redirect(url_for('login_page'))



@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if 'username' in session:
        if request.method == 'POST':
            manager_username = session['username']
            username = request.form['username']
            password = request.form['password']
            department = request.form['department']

            c.execute("INSERT INTO employees (username, password, department) VALUES (?, ?, ?)",
                      (username, password, department))
            conn.commit()
            return redirect(url_for('manager_dashboard'))
        else:
            # Handle GET request to render the form
            return render_template('add_employee.html')
    else:
        return redirect(url_for('login_page'))





@app.route('/assign_task', methods=['GET', 'POST'])
def assign_task():
    if 'username' in session:
        if request.method == 'POST':
            manager_username = session['username']
            employee_username = request.form['employee_username']
            task_name = request.form['task_name']

            c.execute("SELECT * FROM tasks WHERE employee_username = ? AND manager_username = ? AND task_name = ?",
                      (employee_username, manager_username, task_name))
            existing_task = c.fetchone()
            if existing_task:
                return "Task already assigned to the employee."

            c.execute("INSERT INTO tasks (employee_username, manager_username, task_name, progress) VALUES (?, ?, ?, ?)",
                      (employee_username, manager_username, task_name, 0))
            conn.commit()
            return redirect(url_for('manager_dashboard'))
        else:
            # Handle GET request (rendering form or other content)
            # For example, you could render a form to assign a task here
            return render_template('assign_task.html')
    else:
        return redirect(url_for('login_page'))






@app.route('/submit_attendance', methods=['GET', 'POST'])
def submit_attendance():
    if 'username' in session:
        if request.method == 'POST':
            username = session['username']
            status = request.form.get('status')  # Use .get() to safely access the 'status' key
            today = datetime.now().date()
            c.execute("INSERT INTO employee_attendance (employee_username, date, status) VALUES (?, ?, ?)",
                      (username, today, status))
            conn.commit()
            return redirect(url_for('employee_dashboard'))
        else:
            # If the request method is GET, render the attendance submission form
            return render_template('submit_attendance.html')
    else:
        return redirect(url_for('login'))


    
def check_availability(employee_username, manager_username, date, start_time, end_time):
    # Query the availability table to check for conflicting schedules
    c.execute('''SELECT * FROM availability 
                 WHERE employee_username = ? AND manager_username = ? AND date = ?
                 AND ((start_time <= ? AND end_time >= ?) OR (start_time <= ? AND end_time >= ?))''',
              (employee_username, manager_username, date, start_time, start_time, end_time, end_time))
    conflict = c.fetchone()
    if conflict:
        return False  # Conflicting schedule found
    else:
        return True  # No conflicting schedule found

# Route for scheduling meetings on the manager dashboard
@app.route('/manager_dashboard', methods=['GET', 'POST'])
def manager_dashboard():
    if 'username' in session:
        manager_username = session['username']

        if request.method == 'POST':
            employee_username = request.form['username']
            meeting_date = request.form['meeting_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']

            # Check if the meeting date is at least today's date
            today = date.today()
            meeting_date = datetime.strptime(meeting_date, '%Y-%m-%d').date()
            if meeting_date >= today:
                # Check if the employee and manager are available on the meeting date and time
                c.execute("SELECT * FROM availability WHERE employee_username = ? AND manager_username = ? AND date = ? AND start_time = ? AND end_time = ?",
                          (employee_username, manager_username, meeting_date, start_time, end_time))
                availability = c.fetchone()

                if not availability:
                    # Both employee and manager are available, proceed with scheduling the meeting
                    # Insert the meeting into the availability table
                    c.execute("INSERT INTO availability (employee_username, manager_username, date, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                              (employee_username, manager_username, meeting_date, start_time, end_time))
                    conn.commit()
                    # Redirect or render a success message
                    return redirect(url_for('manager_dashboard'))
                else:
                    # The employee or manager is not available at the selected date and time
                    error = 'Employee or manager is not available at the selected date and time.'
            else:
                # The meeting date is not valid (before today's date)
                error = 'Meeting date must be today or later.'

            # Render the manager dashboard with an error message
            c.execute("SELECT * FROM employees")
            employees = c.fetchall()
            employees_with_tasks = []
            for employee in employees:
                c.execute("SELECT * FROM tasks WHERE employee_username = ?", (employee[0],))
                tasks = c.fetchall()
                employees_with_tasks.append((employee, tasks))
            return render_template('manager_dashboard.html', employees_with_tasks=employees_with_tasks, error=error)

        else:
            # Handle GET request for the manager dashboard
            c.execute("SELECT * FROM employees")
            employees = c.fetchall()
            employees_with_tasks = []
            for employee in employees:
                c.execute("SELECT * FROM tasks WHERE employee_username = ?", (employee[0],))
                tasks = c.fetchall()
                employees_with_tasks.append((employee, tasks))
            return render_template('manager_dashboard.html', employees_with_tasks=employees_with_tasks)

    else:
        # Redirect to login if not logged in
        return redirect(url_for('login'))





@app.route('/view_attendance', methods=['GET', 'POST'])
def view_attendance():
    if 'username' in session:
        username = session['username']
        if request.method == 'POST':
            # Assuming the selected date is passed in the form as 'selected_date'
            selected_date = request.form['selected_date']
            # Convert the selected date string to a datetime object
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            # Fetch attendance records for the selected date
            c.execute("SELECT * FROM employee_attendance WHERE date = ?", (selected_date,))

            attendance_records = c.fetchall()

            # Print attendance records for debugging
            print(attendance_records)

            return render_template('view_attendance.html', attendance_records=attendance_records)
        else:
            return render_template('view_attendance.html')
    else:
        return redirect(url_for('login'))




if __name__ == '__main__':
    app.run(debug=True)
