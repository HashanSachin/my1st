import streamlit as st
import psycopg2
import hashlib
from datetime import date
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Smart Finance Cloud Pro", page_icon="💎", layout="wide")

# Database Connection Helper
def get_db_connection():
    if "CLOUD_DB_URL" not in st.secrets:
        st.error("❌ CLOUD_DB_URL missing in Secrets! Please configure Streamlit Secrets.")
        st.stop()
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"])

SECRET_SALT = st.secrets.get("SECRET_SALT", "CloudFinanceForce2026")

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SECRET_SALT.encode('utf-8'), 100000).hex()

# Cloud Database Tables Auto-Creation
@st.cache_resource
def init_cloud_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active'
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                balance NUMERIC NOT NULL DEFAULT 0.0
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS custom_assets (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                asset_name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                estimated_value NUMERIC NOT NULL DEFAULT 0.0
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                tx_date DATE NOT NULL,
                tx_type VARCHAR(20) NOT NULL,
                category VARCHAR(50) NOT NULL,
                amount NUMERIC NOT NULL,
                description TEXT
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(100) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Default Master Admin Creation
        admin_hash = hash_password("admin123")
        c.execute("""
            INSERT INTO users (username, password_hash, role, status)
            VALUES ('admin', %s, 'admin', 'active')
            ON CONFLICT (username) DO NOTHING;
        """, (admin_hash,))

        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"Database Initialization Error: {e}")

init_cloud_db()

# Session State for User Authentication
if "user" not in st.session_state:
    st.session_state.user = None

# --- 1. LOGIN SCREEN ---
if st.session_state.user is None:
    st.title("💎 Smart Finance Cloud")
    st.subheader("Executive Asset & Cashflow Manager")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login to Dashboard")

            if submit:
                p_hash = hash_password(password)
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT id, username, role, status FROM users WHERE username=%s AND password_hash=%s;", (username.strip(), p_hash))
                row = c.fetchone()
                c.close()
                conn.close()

                if row:
                    uid, uname, role, status = row
                    if status == 'inactive':
                        st.error("❌ Your user account is INACTIVE! Contact System Admin.")
                    else:
                        st.session_state.user = {"id": uid, "username": uname, "role": role}
                        
                        # Default Accounts Setup
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s;", (uid,))
                        if c.fetchone()[0] == 0:
                            c.execute("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Main Bank', 'Bank', 0.0);", (uid,))
                            c.execute("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Cash Wallet', 'Cash', 0.0);", (uid,))
                            conn.commit()
                        c.close()
                        conn.close()

                        st.success("Login Successful!")
                        st.rerun()
                else:
                    st.error("Invalid Username or Password!")

# --- 2. MAIN APPLICATION DASHBOARD ---
else:
    st.sidebar.title(f"👤 {st.session_state.user['username']}")
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    st.sidebar.markdown("---")
    
    # Currency Switcher
    currency_choice = st.sidebar.selectbox("Currency Unit", ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"])
    curr_symbol = currency_choice.split()[0]

    # Navigation Options
    menu_items = [
        "📊 Net Worth & Dashboard",
        "🏠 Add Personal Assets",
        "💸 Transactions",
        "🏦 Money Transfer",
        "🔔 Notifications"
    ]
    if st.session_state.user['role'] == 'admin':
        menu_items.append("🔑 Admin Control Panel")

    choice = st.sidebar.radio("Navigation", menu_items)

    # --- Module 1: Dashboard & Net Worth ---
    if choice == "📊 Net Worth & Dashboard":
        st.title("📊 Financial Overview & Net Worth")
        uid = st.session_state.user['id']

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT SUM(balance) FROM accounts WHERE user_id=%s;", (uid,))
        bank_bal = float(c.fetchone()[0] or 0.0)

        c.execute("SELECT SUM(estimated_value) FROM custom_assets WHERE user_id=%s;", (uid,))
        asset_val = float(c.fetchone()[0] or 0.0)
        c.close()
        conn.close()

        net_worth = bank_bal + asset_val

        col1, col2, col3 = st.columns(3)
        col1.metric("💎 Total Net Worth", f"{curr_symbol} {net_worth:,.2f}")
        col2.metric("🏦 Bank Accounts Balance", f"{curr_symbol} {bank_bal:,.2f}")
        col3.metric("🏠 Custom Assets Value", f"{curr_symbol} {asset_val:,.2f}")

    # --- Module 2: Personal Assets ---
    elif choice == "🏠 Add Personal Assets":
        st.title("🏠 Manage Personal Assets (Net Worth)")
        
        with st.form("asset_form"):
            a_name = st.text_input("Asset Name (e.g. Land/Gold)")
            a_cat = st.selectbox("Category", ["Real Estate", "Gold", "Vehicles", "Stocks", "Crypto"])
            a_val = st.number_input("Estimated Value", min_value=0.0, step=100.0)
            btn = st.form_submit_button("➕ Add Asset")

            if btn:
                if a_name and a_val > 0:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s);",
                              (st.session_state.user['id'], a_name, a_cat, a_val))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.success("Asset added successfully!")
                    st.rerun()
                else:
                    st.warning("Please enter valid asset details.")

        st.subheader("Your Personal Assets")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, asset_name, category, estimated_value FROM custom_assets WHERE user_id=%s;", (st.session_state.user['id'],))
        rows = c.fetchall()
        c.close()
        conn.close()

        if rows:
            df = pd.DataFrame(rows, columns=["ID", "Asset Name", "Category", "Value"])
            df["Value"] = df["Value"].apply(lambda x: f"{curr_symbol} {float(x):,.2f}")
            st.dataframe(df, use_container_width=True)

    # --- Module 3: Transactions ---
    elif choice == "💸 Transactions":
        st.title("💸 Record Transactions")
        
        with st.form("tx_form"):
            tx_type = st.selectbox("Type", ["Expense", "Income"])
            tx_amt = st.number_input("Amount", min_value=0.01, step=10.0)
            tx_desc = st.text_input("Description")
            btn = st.form_submit_button("Save Transaction")

            if btn:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT id FROM accounts WHERE user_id=%s LIMIT 1;", (st.session_state.user['id'],))
                acc_row = c.fetchone()
                if acc_row:
                    acc_id = acc_row[0]
                    c.execute("INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, %s, %s, 'General', %s, %s);",
                              (st.session_state.user['id'], acc_id, date.today(), tx_type, tx_amt, tx_desc))
                    bal_change = tx_amt if tx_type == "Income" else -tx_amt
                    c.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (bal_change, acc_id))
                    conn.commit()
                    st.success("Transaction Saved Successfully!")
                else:
                    st.error("No bank account found!")
                c.close()
                conn.close()

    # --- Module 4: Money Transfer ---
    elif choice == "🏦 Money Transfer":
        st.title("🏦 Account-to-Account Money Transfer")
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM accounts WHERE user_id=%s;", (st.session_state.user['id'],))
        acc_names = [r[0] for r in c.fetchall()]
        c.close()
        conn.close()

        if len(acc_names) >= 2:
            with st.form("trf_form"):
                f_acc = st.selectbox("From Account", acc_names, index=0)
                t_acc = st.selectbox("To Account", acc_names, index=1)
                trf_amt = st.number_input("Transfer Amount", min_value=0.01, step=10.0)
                btn = st.form_submit_button("Execute Transfer")

                if btn:
                    if f_acc == t_acc:
                        st.error("From and To accounts must be different!")
                    else:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE accounts SET balance = balance - %s WHERE name=%s AND user_id=%s;", (trf_amt, f_acc, st.session_state.user['id']))
                        c.execute("UPDATE accounts SET balance = balance + %s WHERE name=%s AND user_id=%s;", (trf_amt, t_acc, st.session_state.user['id']))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.success(f"Transferred {curr_symbol} {trf_amt:,.2f} successfully!")
        else:
            st.warning("At least 2 accounts are required to perform a transfer.")

    # --- Module 5: Notifications ---
    elif choice == "🔔 Notifications":
        st.title("🔔 Notifications & Broadcasts")
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, message, created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC;", (st.session_state.user['id'],))
        notifs = c.fetchall()
        c.close()
        conn.close()

        if notifs:
            df = pd.DataFrame(notifs, columns=["ID", "Title", "Message", "Date Created"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No notifications available.")

    # --- Module 6: Admin Panel ---
    elif choice == "🔑 Admin Control Panel" and st.session_state.user['role'] == 'admin':
        st.title("🔑 Master Admin Control Panel")
        tab1, tab2 = st.tabs(["User Management", "Send Broadcast Notification"])

        with tab1:
            st.subheader("Manage User Status")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id, username, role, status FROM users ORDER BY id ASC;")
            users = c.fetchall()
            c.close()
            conn.close()

            df_u = pd.DataFrame(users, columns=["ID", "Username", "Role", "Status"])
            st.dataframe(df_u, use_container_width=True)

            user_list = [u[1] for u in users if u[1] != 'admin']
            if user_list:
                selected_u = st.selectbox("Select User to Toggle Status", user_list)
                if st.button("🔄 Toggle Active/Inactive Status"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT status FROM users WHERE username=%s;", (selected_u,))
                    curr = c.fetchone()[0]
                    nxt = 'inactive' if curr == 'active' else 'active'
                    c.execute("UPDATE users SET status=%s WHERE username=%s;", (nxt, selected_u))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.success(f"User '{selected_u}' status updated to {nxt.upper()}")
                    st.rerun()

        with tab2:
            st.subheader("Send Broadcast")
            with st.form("b_form"):
                b_title = st.text_input("Title")
                b_msg = st.text_area("Message Body")
                btn = st.form_submit_button("📤 Send Broadcast")

                if btn:
                    if b_title and b_msg:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("SELECT id FROM users;")
                        all_u = c.fetchall()
                        for u in all_u:
                            c.execute("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s);", (u[0], b_title, b_msg))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.success("Broadcast sent to all users!")
                    else:
                        st.warning("Please fill in both title and message.")
