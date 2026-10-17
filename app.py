import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import plotly.express as px
import hashlib
import datetime
import uuid

# ==========================================
# 1. APP CONFIGURATION & MODERN UI CSS
# ==========================================
st.set_page_config(page_title="FinMaster Pro", layout="wide", initial_sidebar_state="collapsed")

# Modern, mobile-friendly CSS UI Overhaul
st.markdown("""
    <style>
    /* Main Background & Fonts */
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Modern Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #E2E8F0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        background-color: #2563EB;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    
    /* Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 8px;
        border: 1px solid #CBD5E1;
    }
    
    /* Headers */
    h1, h2, h3 { color: #0F172A; }
    
    /* Dataframes */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE & SECURITY UTILS
# ==========================================
def get_connection():
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)

def run_query(query, params=(), fetch=False, fetch_all=False, commit=True):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        if commit:
            conn.commit()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        st.error(f"Database Error: {e}")
        return None

def hash_password(password):
    salt = st.secrets["SECRET_SALT"]
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()

# ==========================================
# 3. SCHEMA INITIALIZATION
# ==========================================
def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) DEFAULT 'user',
        status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS product_keys (
        id SERIAL PRIMARY KEY, key_code VARCHAR(50) UNIQUE NOT NULL,
        is_used BOOLEAN DEFAULT FALSE, used_by VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(100) NOT NULL, type VARCHAR(50), balance NUMERIC DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
        type VARCHAR(20), amount NUMERIC, category VARCHAR(50), 
        description TEXT, date DATE
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, -- NULL means broadcast
        message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_read BOOLEAN DEFAULT FALSE
    );
    """
    run_query(schema)
    
    # Create master admin if not exists
    admin_check = run_query("SELECT * FROM users WHERE username = 'admin'", fetch=True, commit=False)
    if not admin_check:
        run_query("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')", 
                  ('admin', hash_password('admin123')))

# ==========================================
# 4. AUTHENTICATION (LOGIN / REGISTER)
# ==========================================
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None

def render_auth():
    st.markdown("<h1 style='text-align: center; color: #2563EB;'>FinMaster Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B;'>Enterprise Financial Management</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔒 Login", "📝 Register (Requires Key)"])
        
        with tab1:
            username = st.text_input("Username", key="log_user")
            password = st.text_input("Password", type="password", key="log_pass")
            if st.button("Sign In"):
                user = run_query("SELECT * FROM users WHERE username = %s AND password_hash = %s", 
                                 (username, hash_password(password)), fetch=True)
                if user:
                    if user['status'] == 'inactive':
                        st.error("Account suspended. Contact Administrator.")
                    else:
                        st.session_state.user_id = user['id']
                        st.session_state.username = user['username']
                        st.session_state.role = user['role']
                        st.rerun()
                else:
                    st.error("Invalid credentials.")

        with tab2:
            st.info("Registration requires a one-time Product Key provided by an Admin.")
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            prod_key = st.text_input("Product Key")
            if st.button("Register Account"):
                if new_user and new_pass and prod_key:
                    # Check Product Key
                    key_data = run_query("SELECT * FROM product_keys WHERE key_code = %s AND is_used = FALSE", (prod_key,), fetch=True)
                    if key_data:
                        existing = run_query("SELECT * FROM users WHERE username = %s", (new_user,), fetch=True)
                        if not existing:
                            # Register user
                            run_query("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (new_user, hash_password(new_pass)))
                            # Invalidate Key
                            run_query("UPDATE product_keys SET is_used = TRUE, used_by = %s WHERE key_code = %s", (new_user, prod_key))
                            # Notify Admin
                            admin = run_query("SELECT id FROM users WHERE role = 'admin' LIMIT 1", fetch=True)
                            if admin:
                                run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", 
                                          (admin['id'], f"New user registered: {new_user} via product key."))
                            st.success("Registration successful! You may now login.")
                        else:
                            st.error("Username already exists.")
                    else:
                        st.error("Invalid or already used Product Key.")
                else:
                    st.warning("Please fill all fields.")

# ==========================================
# 5. USER VIEWS
# ==========================================
def render_dashboard(u_id):
    st.subheader("📊 Financial Overview")
    accounts = run_query("SELECT * FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    
    if not accounts:
        st.info("No accounts found. Go to 'Manage Accounts' to add your first account.")
        return

    df_acc = pd.DataFrame(accounts)
    total_balance = df_acc['balance'].sum()
    
    col1, col2 = st.columns(2)
    col1.metric("Total Net Worth", f"${total_balance:,.2f}")
    col2.metric("Active Accounts", len(df_acc))
    
    st.plotly_chart(px.pie(df_acc, names='name', values='balance', title="Asset Distribution", hole=0.4), use_container_width=True)

def render_accounts(u_id):
    st.subheader("💼 Manage Accounts")
    
    # Add Account
    with st.expander("➕ Add New Account"):
        c1, c2, c3 = st.columns(3)
        a_name = c1.text_input("Account Name (e.g., Chase Checking)")
        a_type = c2.selectbox("Type", ["Bank", "Investment", "Cash", "Crypto"])
        a_bal = c3.number_input("Initial Balance", value=0.0, step=10.0)
        if st.button("Create Account"):
            run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s)", (u_id, a_name, a_type, a_bal))
            st.success("Account added!")
            st.rerun()

    # List & Delete Accounts
    accounts = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    if accounts:
        st.markdown("### Existing Accounts")
        for acc in accounts:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{acc['name']}** ({acc['type']})")
            c2.markdown(f"${acc['balance']:,.2f}")
            if c3.button("Delete", key=f"del_acc_{acc['id']}", help="Deletes account and its transactions"):
                run_query("DELETE FROM accounts WHERE id = %s", (acc['id'],))
                st.rerun()

def render_transactions(u_id):
    st.subheader("💸 Transactions")
    accounts = run_query("SELECT id, name FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    
    if not accounts:
        st.warning("You need an account to add transactions.")
        return

    acc_dict = {a['name']: a['id'] for a in accounts}
    
    # Add Transaction
    with st.expander("➕ Add Transaction"):
        c1, c2 = st.columns(2)
        t_acc = c1.selectbox("Account", list(acc_dict.keys()))
        t_type = c2.selectbox("Type", ["Income", "Expense"])
        t_amt = st.number_input("Amount", min_value=0.01, step=10.0)
        t_cat = st.text_input("Category (e.g., Groceries, Salary)")
        t_desc = st.text_input("Description")
        t_date = st.date_input("Date")
        
        if st.button("Save Transaction"):
            acc_id = acc_dict[t_acc]
            run_query("INSERT INTO transactions (user_id, account_id, type, amount, category, description, date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                      (u_id, acc_id, t_type, t_amt, t_cat, t_desc, t_date))
            # Update account balance
            modifier = t_amt if t_type == 'Income' else -t_amt
            run_query("UPDATE accounts SET balance = balance + %s WHERE id = %s", (modifier, acc_id))
            st.success("Transaction saved!")
            st.rerun()

    # View & Edit/Delete Transactions
    st.markdown("### Recent Transactions")
    txns = run_query("""
        SELECT t.id, a.name as account, t.date, t.type, t.category, t.amount, t.description 
        FROM transactions t JOIN accounts a ON t.account_id = a.id 
        WHERE t.user_id = %s ORDER BY t.date DESC
    """, (u_id,), fetch_all=True)

    if txns:
        df_txns = pd.DataFrame(txns)
        st.dataframe(df_txns[['date', 'account', 'type', 'category', 'amount', 'description']], use_container_width=True)
        
        st.markdown("### Edit or Delete a Transaction")
        t_id_to_edit = st.selectbox("Select Transaction ID to Edit/Delete", df_txns['id'].tolist(), format_func=lambda x: f"ID: {x} | {df_txns[df_txns['id']==x]['date'].values[0]} | {df_txns[df_txns['id']==x]['amount'].values[0]}")
        
        c1, c2 = st.columns(2)
        if c1.button("Delete Selected Transaction", type="primary"):
            run_query("DELETE FROM transactions WHERE id = %s", (t_id_to_edit,))
            st.success("Deleted!")
            st.rerun()
            
        with st.expander("Edit Transaction"):
            curr_txn = next(item for item in txns if item["id"] == t_id_to_edit)
            e_type = st.selectbox("Update Type", ["Income", "Expense"], index=0 if curr_txn['type']=='Income' else 1)
            e_amt = st.number_input("Update Amount", value=float(curr_txn['amount']))
            e_cat = st.text_input("Update Category", value=curr_txn['category'])
            e_desc = st.text_input("Update Description", value=curr_txn['description'])
            if st.button("Update"):
                run_query("UPDATE transactions SET type=%s, amount=%s, category=%s, description=%s WHERE id=%s",
                          (e_type, e_amt, e_cat, e_desc, t_id_to_edit))
                st.success("Updated!")
                st.rerun()

def render_settings(u_id):
    st.subheader("⚙️ Account Settings")
    st.markdown("Update your credentials here.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Change Username**")
        new_usr = st.text_input("New Username")
        if st.button("Update Username"):
            check = run_query("SELECT id FROM users WHERE username = %s", (new_usr,), fetch=True)
            if check:
                st.error("Username already taken.")
            else:
                run_query("UPDATE users SET username = %s WHERE id = %s", (new_usr, u_id))
                st.session_state.username = new_usr
                st.success("Username updated!")
                
    with c2:
        st.markdown("**Change Password**")
        new_pw = st.text_input("New Password", type="password")
        if st.button("Update Password"):
            run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_pw), u_id))
            st.success("Password updated!")

def render_notifications(u_id):
    st.subheader("🔔 Notifications")
    notifs = run_query("SELECT * FROM notifications WHERE user_id = %s OR user_id IS NULL ORDER BY date DESC", (u_id,), fetch_all=True)
    if notifs:
        for n in notifs:
            color = "#E0F2FE" if not n['is_read'] else "#F1F5F9"
            st.markdown(f"<div style='background-color: {color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;'>"
                        f"<small>{n['date'].strftime('%Y-%m-%d %H:%M')}</small><br><b>{n['message']}</b></div>", unsafe_allow_html=True)
        if st.button("Mark All as Read"):
            run_query("UPDATE notifications SET is_read = TRUE WHERE user_id = %s OR user_id IS NULL", (u_id,))
            st.rerun()
    else:
        st.info("No notifications.")

# ==========================================
# 6. ADMIN VIEWS
# ==========================================
def render_admin():
    st.subheader("🛡️ Master Admin Panel")
    t1, t2, t3 = st.tabs(["Users & Keys", "Send Notifications", "System Database"])
    
    with t1:
        st.markdown("### Product Keys (Required for Registration)")
        if st.button("Generate New Product Key"):
            new_key = "KEY-" + str(uuid.uuid4()).split('-')[0].upper()
            run_query("INSERT INTO product_keys (key_code) VALUES (%s)", (new_key,))
            st.success(f"Generated Key: {new_key}")
            
        keys = run_query("SELECT * FROM product_keys ORDER BY id DESC LIMIT 10", fetch_all=True)
        if keys:
            st.dataframe(pd.DataFrame(keys))

        st.markdown("### Manage Users")
        users = run_query("SELECT id, username, role, status, created_at FROM users", fetch_all=True)
        df_u = pd.DataFrame(users)
        st.dataframe(df_u)
        
        c1, c2 = st.columns(2)
        del_id = c1.selectbox("Select User ID to Delete", df_u[df_u['role'] != 'admin']['id'].tolist())
        if c1.button("Permanently Delete User", type="primary"):
            run_query("DELETE FROM users WHERE id = %s", (del_id,))
            st.success("User deleted!")
            st.rerun()

    with t2:
        st.markdown("### Send Notification")
        usr_dict = {"Broadcast to All": None}
        for u in users:
            usr_dict[f"{u['id']} - {u['username']}"] = u['id']
            
        target = st.selectbox("Select Recipient", list(usr_dict.keys()))
        msg = st.text_area("Message content")
        if st.button("Send Alert"):
            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (usr_dict[target], msg))
            st.success("Notification sent!")

# ==========================================
# 7. MAIN APP ROUTING
# ==========================================
def main():
    init_db()
    if not st.session_state.user_id:
        render_auth()
    else:
        # Sidebar Navigation
        with st.sidebar:
            st.markdown(f"### Welcome, {st.session_state.username}")
            st.divider()
            page = st.radio("Navigation", ["Dashboard", "Accounts", "Transactions", "Notifications", "Settings", "Admin Panel"] if st.session_state.role == 'admin' else ["Dashboard", "Accounts", "Transactions", "Notifications", "Settings"])
            st.divider()
            if st.button("Log Out", type="primary"):
                st.session_state.clear()
                st.rerun()

        # Page Router
        if page == "Dashboard": render_dashboard(st.session_state.user_id)
        elif page == "Accounts": render_accounts(st.session_state.user_id)
        elif page == "Transactions": render_transactions(st.session_state.user_id)
        elif page == "Notifications": render_notifications(st.session_state.user_id)
        elif page == "Settings": render_settings(st.session_state.user_id)
        elif page == "Admin Panel" and st.session_state.role == "admin": render_admin()

if __name__ == "__main__":
    main()
