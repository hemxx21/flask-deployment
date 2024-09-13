from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc
from datetime import datetime,timedelta
import pandas as pd
from sqlalchemy import create_engine
import os
import hashlib



app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SECRET_KEY']='2004'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'



DATABASE_URI = 'mssql+pyodbc://@test?driver=ODBC+Driver+17+for+SQL+Server;Trusted_Connection=yes;'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def get_db_connection():
    connection = pyodbc.connect(
    'DRIVER={SQL Server};'  
    'SERVER=C3-023\SQLEXPRESS;'  
    'DATABASE=test;'  
    'Trusted_Connection=yes;'
)
    return connection


@app.route('/', methods=['GET', 'POST'])
def login():
    
    
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    
    return render_template('dash.html')
@app.route('/dashboard',methods=['post','get'])
def dashboard():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Hash the entered password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        cursor = get_db_connection().cursor()
        print(hashed_password)
        
        query="SELECT UserId,Is_supplier,VendorCode FROM credentials WHERE UserName = ? AND Password = ?"
        cursor.execute(query,(username,hashed_password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['is_supplier'] = user[1]  # Store Is_supplier status in session
            session['vendor_code'] = user[2]  # Store VendorCode in session

            # Check if the user is a supplier
            if user[1]:  # If Is_supplier is 1 (True)
                return redirect(url_for('vendor'))
            else:
                return redirect(url_for('home'))
        else:
            error = 'Invalid username or password. Please try again.'
    return render_template('login.html', error=error)

@app.route('/vendor', methods=['POST', 'GET'])
def vendor():
    # Ensure the user is logged in and has a vendor code
    if 'vendor_code' not in session:
        return redirect(url_for('dashboard'))
    
    vendor_code = session['vendor_code']  # Get the vendor code from the session
    
    # Get the number of rows per page from the dropdown, default to 10 if not specified
    rows_per_page = request.args.get('rows_per_page', '10')
    page = request.args.get('page', '1')

    # Validate and convert rows_per_page
    if rows_per_page.isdigit():
        rows_per_page = int(rows_per_page)
    else:
        rows_per_page = 10  # Default value if not provided or invalid

    # Validate and convert page
    if page.isdigit():
        page = int(page)
    else:
        page = 1  # Default value if not provided or invalid
    
    # Calculate the offset for the SQL query
    offset = (page - 1) * rows_per_page

    # Get the database connection and cursor
    connection = get_db_connection()
    cursor = connection.cursor()

    # Fetch data only for the logged-in supplier's vendor code with pagination
    query = """
        EXEC [dbo].[getSCMdata] @vendor_code = ?, @offset = ?, @rows_per_page = ?
    """
    cursor.execute(query, (vendor_code, offset, rows_per_page))
    rows = cursor.fetchall()

    # Convert rows to a list of dictionaries and handle NULL and 0.0 values
    data = []
    for row in rows:
        row_dict = {}
        for col_name, value in zip(cursor.description, row):
            # Replace NULL with empty string
            if value is None:
                row_dict[col_name[0]] = ''
            # Replace 0.0 in integer or float fields with an empty string
            elif isinstance(value, float) and value == 0.0:
                row_dict[col_name[0]] = ''
            else:
                row_dict[col_name[0]] = value
        data.append(row_dict)

    # Fetch total number of rows for pagination (filtered by VendorCode)
    cursor.execute("""
        SELECT COUNT(*) FROM PendingPurchaseOrder 
        WHERE liveorder = 1 AND VendorCode = ? AND (astcat <> 'K' OR astcat IS NULL)
    """, (vendor_code,))
    total_rows = cursor.fetchone()[0]

    # Fetch status codes and descriptions
    cursor.execute("SELECT StatusCode, StatusDescription FROM StatusMaster")
    statuses = cursor.fetchall()

    # Calculate the total number of pages
    total_pages = (total_rows + rows_per_page - 1) // rows_per_page

    number_of_records = len(data)
    column_names = [desc[0] for desc in cursor.description]
    
    # Close the cursor and connection
    cursor.close()
    connection.close()

    # Render the vendor.html template with the relevant data
    return render_template('vendor.html',
                           number_of_records=number_of_records,
                           data=data,
                           statuses=statuses,
                           column_names=column_names,
                           total_pages=total_pages,
                           page=page,
                           rows_per_page=rows_per_page)


@app.route('/scm', methods=['POST', 'GET'])
def scm():

    # Ensure the user is logged in
    if 'vendor_code' not in session:
        return redirect(url_for('dashboard'))
    
    vendor_code = session['vendor_code']  # Get the vendor code from the session

    # Get the number of rows per page from the dropdown, default to 10 if not specified
    rows_per_page = request.args.get('rows_per_page', '10')
    page = request.args.get('page', '1')

    # Validate and convert rows_per_page
    if rows_per_page.isdigit():
        rows_per_page = int(rows_per_page)
    else:
        rows_per_page = 10  # Default value if not provided or invalid

    # Validate and convert page
    if page.isdigit():
        page = int(page)
    else:
        page = 1  # Default value if not provided or invalid
    
    # Calculate the offset for the SQL query
    offset = (page - 1) * rows_per_page

    connection = get_db_connection()
    cursor = connection.cursor()

    # Modify the query to handle NULL vendor_code (if vendor_code is NULL, return all rows)
    query = """
        EXEC [dbo].[getSCMdata] @vendor_code = ?, @offset = ?, @rows_per_page = ?
    """
    if vendor_code:
        cursor.execute(query, (vendor_code, offset, rows_per_page))
    else:
        cursor.execute(query, (None, offset, rows_per_page))  # Pass None or NULL to fetch all data
    
    rows = cursor.fetchall()

    # Convert rows to a list of dictionaries and handle NULL and 0.0 values
    data = []
    for row in rows:
        row_dict = {}
        for col_name, value in zip(cursor.description, row):
            # Replace NULL with empty string
            if value is None:
                row_dict[col_name[0]] = ''
            # Replace 0.0 in integer or float fields with an empty string
            elif isinstance(value, float) and value == 0.0:
                row_dict[col_name[0]] = ''
            else:
                row_dict[col_name[0]] = value
        data.append(row_dict)

    # Fetch total number of rows for pagination
    cursor.execute("SELECT COUNT(*) FROM PendingPurchaseOrder WHERE liveorder = 1 AND (astcat <> 'K' OR astcat IS NULL)")
    total_rows = cursor.fetchone()[0]
    
    # Calculate the total number of pages
    total_pages = (total_rows + rows_per_page - 1) // rows_per_page

    number_of_records = len(data)
    column_names = [desc[0] for desc in cursor.description]
    cursor.close()
    connection.close()

    # Fetch VendorName
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT DISTINCT VendorName from PendingPurchaseOrder"
    cursor.execute(query)
    fnd_name = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()

    # Fetch plant names
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT * FROM plant"
    cursor.execute(query)
    plant_name = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()

    # Fetch MRPController
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT DISTINCT MRPController FROM PendingPurchaseOrder"
    cursor.execute(query)
    pdt_name = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()

    return render_template(
        'scm_upd.html',
        number_of_records=number_of_records,
        data=data,
        column_names=column_names,
        plant_name=plant_name,
        fnd_name=fnd_name,
        pdt_name=pdt_name,
        total_pages=total_pages,
        page=page, 
        rows_per_page=rows_per_page 
    )

@app.route('/scm/history/<doc>/<item>', methods=['GET'])
def scm_history_page(doc, item):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor()

    # Execute the stored procedure to fetch history data
    query = """
        EXEC [dbo].[spGetSCMDataHistory] @GlobalPurDocument = ?, @GlobalPurItem = ?
    """
    cursor.execute(query, (doc, item))
    history_data = cursor.fetchall()

    # Convert history data into a list of dictionaries
    data = []
    for row in history_data:
        row_dict = {}
        for col_name, value in zip(cursor.description, row):
            row_dict[col_name[0]] = value if value is not None else ''
        data.append(row_dict)

    cursor.close()
    connection.close()

    # Render the history page
    return render_template('scm_history.html', data=data, doc=doc, item=item)


def normalize_numeric(value):
    try:
        return "0.0" if value is None else str(float(value))
    except ValueError:
        return "0.0"

def normalize_date(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(value, str) and value.strip():
        try:
            # Try to parse the string with a full datetime format
            date_obj = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                # Try to parse the string with a date-only format and add a default time
                date_obj = datetime.strptime(value, '%Y-%m-%d')
                return date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    # Try to parse the string with a day/month/year format
                    date_obj = datetime.strptime(value, '%d/%m/%Y')
                    return date_obj.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return None
        else:
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return None


def normalize_text(value):
    return "" if value is None else value

# Normalize empty values to a common format 
def normalize_status(status):
    if status in [None, '', '0']:
        return 0
    return status

@app.route('/executeven/<int:num_records>', methods=['POST'])
def executeven(num_records):
    page = request.form.get('page', '1')  # Get the current page number
    rows_per_page = request.form.get('rows_per_page', '10')  # Get the rows per page

    connection = get_db_connection()
    cursor = connection.cursor()

    for i in range(1, num_records + 1):
        record_id = request.form.get(f'record_id_{i}')
        item_id = request.form.get(f'item_id_{i}')
        delivery_date = request.form.get(f'delivery_date_{i}')
        new_sample_qty = normalize_numeric(request.form.get(f'SampleQty_{i}'))
        new_date = normalize_date(request.form.get(f'date_{i}'))
        status = normalize_text(request.form.get(f'status_{i}'))
        new_L1Qty = normalize_numeric(request.form.get(f'L1Qty_{i}'))
        new_L1date = normalize_date(request.form.get(f'L1Date_{i}'))
        new_L1status = normalize_status(request.form.get(f'L1Status_{i}'))
        new_L2qty = normalize_numeric(request.form.get(f'L2Qty_{i}'))
        new_L2date = normalize_date(request.form.get(f'L2Date_{i}'))
        new_L2status = normalize_status(request.form.get(f'L2Status_{i}'))
        new_L3qty = normalize_numeric(request.form.get(f'L3Qty_{i}'))
        new_L3date = normalize_date(request.form.get(f'L3Date_{i}'))
        print('L3 date:'+str(new_L3date))
        new_L3status = normalize_status(request.form.get(f'L3Status_{i}'))
        new_OAnumber = normalize_text(request.form.get(f'OANumber_{i}'))
        new_remarks = normalize_text(request.form.get(f'SupplierRemarks_{i}'))

        try:
            delivery_date = datetime.strptime(delivery_date, '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError as e:
            print(f"Date format error for record {record_id}: {e}")
            continue  # Skip this record if the date conversion fails

        cursor.execute("""
            SELECT SQty, SDate, SStatusCode, L1Qty, L1Date, L1StatusCode, L2Qty, L2Date, L2StatusCode, L3Qty, L3Date, L3StatusCode, OANumber, SupplierRemarks 
            FROM PendingPurchaseOrder 
            WHERE PurchaseDocument = ? AND PurchaseDocumentItem = ? AND DeliveryDate = ?
        """, (record_id,item_id, delivery_date))
        
        row = cursor.fetchone()
        

        if row:
            c_sqty, c_sdate, c_status, c_l1qty, c_l1date, c_l1status, c_l2qty, c_l2date, c_l2status, c_l3qty, c_l3date, c_l3status, c_oanum, c_remarks = row

            print(new_date,c_sdate)
            print(new_L1date,c_l1date)
            print(new_L2date,c_l2date)

            # Normalize database values
            c_sqty = normalize_numeric(c_sqty)
            c_sdate = normalize_date(c_sdate)
            c_status = normalize_text(c_status)
            c_l1qty = normalize_numeric(c_l1qty)
            c_l1date = normalize_date(c_l1date)
            c_l1status = normalize_status(c_l1status)
            c_l2qty = normalize_numeric(c_l2qty)
            c_l2date = normalize_date(c_l2date)
            c_l2status = normalize_status(c_l2status)
            c_l3qty = normalize_numeric(c_l3qty)
            c_l3date = normalize_date(c_l3date)
            c_l3status = normalize_status(c_l3status)
            c_oanum = normalize_text(c_oanum)
            c_remarks = normalize_text(c_remarks)


            '''# Check if any of the columns have actually changed
            def dates_equal(date1, date2):
                # Consider None or empty string as equal
                return (date1 is None and date2 in [None, ""]) or (date2 is None and date1 in [None, ""]) or (date1 == date2)'''
            
            def dates_equal(date1, date2):
                # Convert to datetime object, ensure None and empty string are treated equally
                def to_datetime(date):
                    if date is None or date == "":
                        return None
                    if isinstance(date, datetime):
                        return date
                    try:
                        return datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            return datetime.strptime(date, '%Y-%m-%d')
                        except ValueError:
                            return None

                # Convert both dates
                dt1 = to_datetime(date1)
                dt2 = to_datetime(date2)

                return dt1 == dt2



            # Check if any of the columns have actually changed
            if ((new_sample_qty != c_sqty) or 
                (not dates_equal(new_date, c_sdate)) or 
                (status != c_status) or 
                (new_L1Qty != c_l1qty) or 
                (not dates_equal(new_L1date, c_l1date)) or 
                (new_L1status != c_l1status) or
                (new_L2qty != c_l2qty) or 
                (not dates_equal(new_L2date, c_l2date)) or 
                (new_L2status != c_l2status) or
                (new_L3qty != c_l3qty) or 
                (not dates_equal(new_L3date, c_l3date)) or 
                (new_L3status != c_l3status) or
                (new_OAnumber != c_oanum) or 
                (new_remarks != c_remarks)):

                # Update only if there are changes
                last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # Normalize date comparison in SQL
                query = """
    UPDATE PendingPurchaseOrder 
SET SQty = ?, 
    SDate = CASE WHEN ? IS NULL THEN NULL ELSE CONVERT(DATE, ?) END, 
    SStatusCode = ?, 
    L1Qty = ?, 
    L1Date = CASE WHEN ? IS NULL THEN NULL ELSE CONVERT(DATE, ?) END, 
    L1StatusCode = ?, 
    L2Qty = ?, 
    L2Date = CASE WHEN ? IS NULL THEN NULL ELSE CONVERT(DATE, ?) END, 
    L2StatusCode = ?, 
    L3Qty = ?, 
    L3Date = CASE WHEN ? IS NULL THEN NULL ELSE CONVERT(DATE, ?) END, 
    L3StatusCode = ?, 
    OANumber = ?, 
    SupplierRemarks = ?, 
    UpdatedDateTime = ? 
WHERE PurchaseDocument = ? 
  AND PurchaseDocumentItem = ? 
  AND DeliveryDate = CONVERT(DATE, ?)
  AND (SQty <> ? 
    OR (SDate IS NULL AND ? IS NOT NULL) OR (SDate IS NOT NULL AND CONVERT(DATE, SDate) <> CONVERT(DATE, ?))
    OR SStatusCode <> ? 
    OR L1Qty <> ? 
    OR (L1Date IS NULL AND ? IS NOT NULL) OR (L1Date IS NOT NULL AND CONVERT(DATE, L1Date) <> CONVERT(DATE, ?))
    OR L1StatusCode <> ? 
    OR L2Qty <> ? 
    OR (L2Date IS NULL AND ? IS NOT NULL) OR (L2Date IS NOT NULL AND CONVERT(DATE, L2Date) <> CONVERT(DATE, ?))
    OR L2StatusCode <> ? 
    OR L3Qty <> ? 
    OR (L3Date IS NULL AND ? IS NOT NULL) OR (L3Date IS NOT NULL AND CONVERT(DATE, L3Date) <> CONVERT(DATE, ?))
    OR L3StatusCode <> ? 
    OR OANumber <> ? 
    OR SupplierRemarks <> ?)

"""
               
                try:
                    cursor.execute(query, (
        # SET Clause Parameters
        new_sample_qty, new_date, new_date, status, 
        new_L1Qty, new_L1date, new_L1date, new_L1status, 
        new_L2qty, new_L2date, new_L2date, new_L2status, 
        new_L3qty, new_L3date, new_L3date, new_L3status, 
        new_OAnumber, new_remarks, last_updated, 
        
        # WHERE Clause Parameters
        record_id, item_id, delivery_date, 
        new_sample_qty, new_date, new_date, status, 
        new_L1Qty, new_L1date, new_L1date, new_L1status, 
        new_L2qty, new_L2date, new_L2date, new_L2status, 
        new_L3qty, new_L3date, new_L3date, new_L3status, 
        new_OAnumber, new_remarks
    ))

                    connection.commit()
                except Exception as e:
                    print(f"Error updating record {record_id}: {e}")

    print("Changes committed to the database.")
    return redirect(url_for('vendor', page=page, rows_per_page=rows_per_page))


@app.route('/execute/<int:num_records>', methods=['POST'])
def execute(num_records):
    connection = get_db_connection()
    cursor = connection.cursor()

    for i in range(1, num_records + 1):
        record_id = request.form.get(f'record_id_{i}')
        item_id = request.form.get(f'item_id_{i}')
        delivery_date = request.form.get(f'delivery_date_{i}')
        new_urgent_status = request.form.get(f'urgent_{i}')
        new_remarks = request.form.get(f'LTVLRemarks_{i}')

        # Debug prints to check retrieved data
        print(f"Processing record {record_id} with Urgent: {new_urgent_status}, Remarks: {new_remarks}")

        try:
            delivery_date = datetime.strptime(delivery_date, '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError as e:
            print(f"Date format error for record {record_id}: {e}")
            continue  # Skip this record if the date conversion fails

        # Fetch current values
        cursor.execute("""
            SELECT Urgent, LTVLRemarks 
            FROM PendingPurchaseOrder 
            WHERE PurchaseDocument = ? AND PurchaseDocumentItem = ? AND DeliveryDate = ?
        """, (record_id, item_id, delivery_date))        
        row = cursor.fetchone()

        if row:
            current_urgent_status, current_remarks = row
            if (new_urgent_status != current_urgent_status) or (new_remarks != current_remarks):
                last_updated = datetime.now()
                query = """
                    UPDATE PendingPurchaseOrder 
                    SET Urgent = ?, LTVLRemarks = ?, UpdatedDateTime = ? 
                    WHERE PurchaseDocument = ? AND PurchaseDocumentItem = ? AND DeliveryDate = ?
                """

                try:
                    cursor.execute(query, (new_urgent_status, new_remarks, last_updated, record_id, item_id, delivery_date))
                    connection.commit()
                    print(f"Updated record {record_id}")
                except Exception as e:
                    print(f"Error updating record {record_id}: {e}")
        
        # Call the stored procedure to insert history
            query = """
                EXEC [dbo].[spInsertPendingPurchaseOrderHistory] @PurchaseDocument = ?, @PurchaseDocumentItem = ?
            """
            cursor.execute(query, (record_id, item_id))
    
    # Commit the transaction
    connection.commit()

    try:
        
        print("Changes committed to the database.")
    except Exception as e:
        print(f"Error committing changes: {e}")

   

    return redirect('/scm')



@app.route('/filter_data', methods=['POST', 'GET'])
def filter_data():
    rows_per_page = request.args.get('rows_per_page', '25')
    page = request.args.get('page', '1')

    # Validate and convert rows_per_page
    if rows_per_page.isdigit():
        rows_per_page = int(rows_per_page)
    else:
        rows_per_page = 25  # Default value if not provided or invalid

    # Validate and convert page
    if page.isdigit():
        page = int(page)
    else:
        page = 1  # Default value if not provided or invalid
    
    # Calculate the offset for the SQL query
    offset = (page - 1) * rows_per_page

    connection = get_db_connection()
    cursor = connection.cursor()
    query = f"""
            SELECT * 
            FROM pendingpurchaseorder 
            ORDER BY VendorName
            OFFSET {offset} ROWS 
            FETCH NEXT {rows_per_page} ROWS ONLY;
        """   
    cursor.execute(query)
    data = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM pendingpurchaseorder")
    total_rows = cursor.fetchone()[0]
    number_of_records = len(data)
    # Calculate the total number of pages
    total_pages = (total_rows + rows_per_page - 1) // rows_per_page

    selected_plants = request.form.getlist('plants')
    selected_fnd = request.form.getlist('fnd')
    selected_pdt = request.form.getlist('productGroup')

    connection = get_db_connection()
    cursor = connection.cursor()
    
    query = "SELECT * FROM PendingPurchaseOrder WHERE 1=1"
    params = []

    if selected_plants:
        plants_placeholder = ', '.join(['?'] * len(selected_plants))
        query += f" AND plant IN ({plants_placeholder})"
        params.extend(selected_plants)
    

    if selected_fnd:
        fnd_placeholder = ', '.join(['?'] * len(selected_fnd))
        query += f" AND VendorName IN ({fnd_placeholder})"
        params.extend(selected_fnd)

    if selected_pdt:
        pdt_placeholder = ', '.join(['?'] * len(selected_pdt))
        query += f" AND MRPController IN ({pdt_placeholder})"
        params.extend(selected_pdt)

    print(selected_plants)
    print(selected_pdt)
    print(selected_fnd)
    cursor.execute(query, params)
    data = cursor.fetchall()

    column_names = [desc[0] for desc in cursor.description]

    cursor.execute("SELECT VendorName FROM PendingPurchaseOrder")
    data1 = cursor.fetchall()
    fnd_name = [row[0] for row in data1]

    cursor.execute("SELECT * FROM plant")
    data3 = cursor.fetchall()
    plant_name = [row[0] for row in data3]

    cursor.execute("SELECT DISTINCT MRPController FROM PendingPurchaseOrder")
    data2 = cursor.fetchall()
    pdt_name = [row[0] for row in data2]

    connection.close()

    return render_template('scm_upd.html', number_of_records=number_of_records,data=data, column_names=column_names, plant_name=plant_name, fnd_name=fnd_name, pdt_name=pdt_name, total_pages=total_pages, page=page, rows_per_page=rows_per_page)


@app.route('/data_import', methods=['POST', 'GET'])
def data_import():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)
            df = pd.read_excel(filename)

            date_columns = ['PO crd. date', 'Delivery date', 'CDD']

            # Convert the date columns to datetime objects
            for column in date_columns:
                df[column] = pd.to_datetime(df[column], format='%d-%m-%Y')

            # Convert the datetime columns back to string format (if needed)
            for column in date_columns:
                df[column] = df[column].dt.strftime('%Y-%m-%d %H:%M:%S')

            # Convert float columns, handle NaNs, empty strings and round
            float_columns = ['Scheduled Qty', 'GR Qty', 'Open Qty', 'Cast Weight']
            for col in float_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')  # Convert to float, coerce errors to NaN
                df[col] = df[col].fillna(0.0)  # Replace NaNs with 0.0
                df[col] = df[col].replace('', 0.0)  # Replace empty strings with 0.0
                df[col] = df[col].astype(float)  # Ensure type is float64
                df[col] = df[col].round(2)  # Round to 2 decimal places

            # Ensure Sales order is treated as string
            df['Sales order'] = df['Sales order'].apply(lambda x: str(int(x)) if pd.notnull(x) else None)
            df['Sales order item'] = df['Sales order item'].apply(lambda x: str(int(x)) if pd.notnull(x) else None)
            # Replace NaNs with None for database insertion
            df = df.where(pd.notnull(df), None)

            conn = get_db_connection()
            cursor = conn.cursor()  

            
            cursor.execute("EXEC [dbo].[delPOExcelTable]")
            conn.commit()

            

            # Insert data into SQL Server
            for index, row in df.iterrows():

                try:
                    cursor.execute(
                        """
                        INSERT INTO [PendingPurchaseOrderExcel] (
                            [POType], [PurchaseDocument], [PurchaseDocumentItem], [DocDate], [AstCat], 
                            [VendorCode], [VendorName], [Material], [MaterialDescription], [OUN], 
                            [ScheduleQty], [DeliveryDate], [DeliveredQty], [OpenQty], [Plant], 
                            [MRPController], [PurchaseGroup], [PurchaseGroupName], [DrgNo], 
                            [CustomerProjectName], [IndustryStdDesc], [SalesDocument], 
                            [SalesOrderItem], [CDD], [ShipToCode], [ShipToName], [CastWt]
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row['PO type'], row['PO number'], row['Item no.'], row['PO crd. date'], row['Acc. ast. cat.'],
                            row['Vendor code'], row['Vendor name'], row['Material code'], row['Material Description'], row['UOM'],
                            row['Scheduled Qty'], row['Delivery date'], row['GR Qty'], row['Open Qty'], row['Plant'],
                            row['MRP Cont.'], row['Purchase goup'], row['Purc. group name'], row['Drg No.'],
                            row['Customer project name'], row['Component name'], row['Sales order'],
                            row['Sales order item'], row['CDD'], row['Ship to party'], row['Ship to party name'], row['Cast Weight']
                        )
                    )
                except pyodbc.ProgrammingError as e:
                    print(f"Error inserting row {index}: {e}")
                    continue  # Skip problematic rows and continue

            conn.commit()
            # Execute the stored procedure to update the PendingPurchaseOrder table
            cursor.execute("EXEC [dbo].[updatepo]")
            conn.commit()
            conn.close()

            return 'Table created successfully!'

    return render_template('data_import.html')


if __name__ == '__main__':
    app.run(debug=True)
