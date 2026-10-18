import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import plotly.express as px
import hashlib
import uuid

# ==========================================
# 1. APP CONFIGURATION & MOBILE-APP CSS
# ==========================================
st.set_page_config(page_title="FinMaster Pro", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Main Background & Fonts */
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* Hide Streamlit Branding & Sidebar completely */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="collapsedControl"] {display: none;}
    
    /* Dashboard Nav Buttons (Big App-like Buttons) */
    .nav-btn {
        width: 100%;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: 600;
        padding: 15px 10px;
        transition: all 0.2s ease-in-out;
        border: none;
    }
    
    /* Primary Action Buttons */
    button[kind="primary"] {
        background-color: #2563EB !important;
        color: white !important;
    }
    button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #E2E8F0;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 10px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. STATE MANAGEMENT & NAVIGATION
# ==========================================
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'

def change_page(page_name):
    st.session_state.current_page = page_name

# ==========================================
# 3. DATABASE UTILS
# ==========================================
def get_connection():
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)

def run_query(query, params=(), fetch=False, fetch_all=False, commit=True):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch: result = cur.fetchone()
        elif fetch_all: result = cur.fetchall()
        if commit: conn.commit()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        st.error(f"Database Error: {e}")
        return None

def hash_password(password):
    salt = st.secrets["SECRET_SALT"]
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()

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
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_read BOOLEAN DEFAULT FALSE
    );
    """
    run_query(schema)
    if not run_query("SELECT * FROM users WHERE username = 'admin'", fetch=True, commit=False):
        run_query("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')", 
                  ('admin', hash_password('admin123')))

# ==========================================
# 4. AUTHENTICATION
# ==========================================
def render_auth():
    st.markdown("<h1 style='text-align: center; color: #0F172A; margin-top: 2rem;'>FinMaster</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B;'>Secure Financial Hub</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔒 Login", "📝 Register Key"])
    with tab1:
        username = st.text_input("Username", key="log_user")
        password = st.text_input("Password", type="password", key="log_pass")
        if st.button("Sign In", type="primary"):
            user = run_query("SELECT * FROM users WHERE username = %s AND password_hash = %s", 
                             (username, hash_password(password)), fetch=True)
            if user:
                if user['status'] == 'inactive':
                    st.error("Account suspended.")
                else:
                    st.session_state.user_id = user['id']
                    st.session_state.username = user['username']
                    st.session_state.role = user['role']
                    st.session_state.current_page = 'Home'
                    st.rerun()
            else:
                st.error("Invalid credentials.")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        prod_key = st.text_input("Product Key")
        if st.button("Register Account", type="primary"):
            if new_user and new_pass and prod_key:
                if run_query("SELECT * FROM product_keys WHERE key_code = %s AND is_used = FALSE", (prod_key,), fetch=True):
                    if not run_query("SELECT * FROM users WHERE username = %s", (new_user,), fetch=True):
                        run_query("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (new_user, hash_password(new_pass)))
                        run_query("UPDATE product_keys SET is_used = TRUE, used_by = %s WHERE key_code = %s", (new_user, prod_key))
                        admin = run_query("SELECT id FROM users WHERE role = 'admin' LIMIT 1", fetch=True)
                        if admin:
                            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", 
                                      (admin['id'], f"New registration: {new_user}"))
                        st.success("Registered! You may now log in.")
                    else: st.error("Username exists.")
                else: st.error("Invalid or used Key.")
            else: st.warning("Fill all fields.")

# ==========================================
# 5. APP SCREENS
# ==========================================
def render_header(title):
    col1, col2 = st.columns([1, 4])
    with col1:
        st.button("⬅️ Back", on_click=change_page, args=('Home',), type="secondary")
    with col2:
        st.subheader(title)
    st.markdown("---")

def render_home(u_id):
    st.markdown(f"## 👋 Hello, {st.session_state.username}")
    
    # Check notifications
    unread = run_query("SELECT COUNT(*) as c FROM notifications WHERE (user_id = %s OR user_id IS NULL) AND is_read = FALSE", (u_id,), fetch=True)
    if unread and unread['c'] > 0:
        st.info(f"You have {unread['c']} unread notification(s).")

    # Main Metrics
    accounts = run_query("SELECT balance FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    total_balance = sum(a['balance'] for a in accounts) if accounts else 0.0
    
    st.metric("Total Net Worth", f"${total_balance:,.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # App Navigation Grid
    c1, c2 = st.columns(2)
    with c1:
        st.button("💼 Accounts", on_click=change_page, args=('Accounts',))
        st.button("💸 Transactions", on_click=change_page, args=('Transactions',))
    with c2:
        st.button("🔔 Notifications", on_click=change_page, args=('Notifications',))
        st.button("⚙️ Settings", on_click=change_page, args=('Settings',))
        
    if st.session_state.role == 'admin':
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🛡️ Master Admin Panel", on_click=change_page, args=('Admin',), type="primary")
        
    st.markdown("<br><hr>", unsafe_allow_html=True)
    if st.button("🚪 Log Out"):
        st.session_state.clear()
        st.rerun()

def render_accounts(u_id):
    render_header("💼 Manage Accounts")
    
    with st.expander("➕ Add New Account"):
        a_name = st.text_input("Account Name")
        a_type = st.selectbox("Type", ["Bank", "Investment", "Cash", "Crypto"])
        a_bal = st.number_input("Initial Balance", value=0.0)
        if st.button("Create", type="primary"):
            run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s)", (u_id, a_name, a_type, a_bal))
            st.success("Added!")
            st.rerun()

    accounts = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    if accounts:
        for acc in accounts:
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{acc['name']}** - ${acc['balance']:,.2f}")
            if c2.button("Delete", key=f"del_{acc['id']}"):
                run_query("DELETE FROM accounts WHERE id = %s", (acc['id'],))
                st.rerun()

def render_transactions(u_id):
    render_header("💸 Transactions")
    
    accounts = run_query("SELECT id, name FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    if not accounts:
        st.warning("Add an account first.")
        return

    acc_dict = {a['name']: a['id'] for a in accounts}
    
    with st.expander("➕ New Transaction"):
        t_acc = st.selectbox("Account", list(acc_dict.keys()))
        t_type = st.selectbox("Type", ["Income", "Expense"])
        t_amt = st.number_input("Amount", min_value=0.01)
        t_cat = st.text_input("Category")
        t_desc = st.text_input("Description")
        t_date = st.date_input("Date")
        if st.button("Save", type="primary"):
            acc_id = acc_dict[t_acc]
            run_query("INSERT INTO transactions (user_id, account_id, type, amount, category, description, date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                      (u_id, acc_id, t_type, t_amt, t_cat, t_desc, t_date))
            mod = t_amt if t_type == 'Income' else -t_amt
            run_query("UPDATE accounts SET balance = balance + %s WHERE id = %s", (mod, acc_id))
            st.success("Saved!")
            st.rerun()

    txns = run_query("""
        SELECT t.id, a.name as acc, t.date, t.type, t.amount, t.description 
        FROM transactions t JOIN accounts a ON t.account_id = a.id 
        WHERE t.user_id = %s ORDER BY t.date DESC
    """, (u_id,), fetch_all=True)

    if txns:
        st.markdown("### Edit/Delete Records")
        t_id = st.selectbox("Select Record", [t['id'] for t in txns], format_func=lambda x: f"[{x}] {next(t['date'] for t in txns if t['id']==x)} | ${next(t['amount'] for t in txns if t['id']==x)}")
        curr = next(t for t in txns if t['id'] == t_id)
        
        c1, c2 = st.columns(2)
        e_type = c1.selectbox("Type", ["Income", "Expense"], index=0 if curr['type']=='Income' else 1, key="e_t")
        e_amt = c2.number_input("Amount", value=float(curr['amount']), key="e_a")
        
        c3, c4 = st.columns(2)
        if c3.button("Update", type="primary"):
            run_query("UPDATE transactions SET type=%s, amount=%s WHERE id=%s", (e_type, e_amt, t_id))
            st.success("Updated!")
            st.rerun()
        if c4.button("Delete"):
            run_query("DELETE FROM transactions WHERE id=%s", (t_id,))
            st.rerun()

def render_settings(u_id):
    render_header("⚙️ Settings")
    st.markdown("**Change Username**")
    new_u = st.text_input("New Username")
    if st.button("Update Username", type="primary"):
        if run_query("SELECT id FROM users WHERE username = %s", (new_u,), fetch=True):
            st.error("Taken.")
        else:
            run_query("UPDATE users SET username = %s WHERE id = %s", (new_u, u_id))
            st.session_state.username = new_u
            st.success("Updated!")
            
    st.markdown("---")
    st.markdown("**Change Password**")
    new_p = st.text_input("New Password", type="password")
    if st.button("Update Password", type="primary"):
        run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_p), u_id))
        st.success("Updated!")

def render_notifications(u_id):
    render_header("🔔 Notifications")
    notifs = run_query("SELECT * FROM notifications WHERE user_id = %s OR user_id IS NULL ORDER BY date DESC", (u_id,), fetch_all=True)
    if notifs:
        if st.button("Mark All Read", type="primary"):
            run_query("UPDATE notifications SET is_read = TRUE WHERE user_id = %s OR user_id IS NULL", (u_id,))
            st.rerun()
        for n in notifs:
            bg = "#E0F2FE" if not n['is_read'] else "#ffffff"
            st.markdown(f"<div style='background: {bg}; padding:15px; border-radius:10px; border:1px solid #e2e8f0; margin-bottom:10px;'>"
                        f"<small style='color:gray;'>{n['date'].strftime('%Y-%m-%d')}</small><br><b>{n['message']}</b></div>", unsafe_allow_html=True)
    else:
        st.info("Inbox empty.")

def render_admin():
    render_header("🛡️ Admin Panel")
    
    with st.expander("🔑 Generate Product Keys"):
        if st.button("Create Key", type="primary"):
            new_key = "KEY-" + str(uuid.uuid4()).split('-')[0].upper()
            run_query("INSERT INTO product_keys (key_code) VALUES (%s)", (new_key,))
            st.success(f"Key: {new_key}")
        keys = run_query("SELECT * FROM product_keys ORDER BY id DESC LIMIT 5", fetch_all=True)
        if keys: st.dataframe(pd.DataFrame(keys))

    with st.expander("👤 Manage Users"):
        users = run_query("SELECT id, username, role FROM users", fetch_all=True)
        df_u = pd.DataFrame(users)
        st.dataframe(df_u)
        del_id = st.selectbox("Delete User ID", df_u[df_u['role'] != 'admin']['id'].tolist())
        if st.button("Permanently Delete User"):
            run_query("DELETE FROM users WHERE id = %s", (del_id,))
            st.rerun()

    with st.expander("📢 Send Alerts"):
        usr_dict = {"All (Broadcast)": None}
        for u in users: usr_dict[f"{u['username']} (ID:{u['id']})"] = u['id']
        target = st.selectbox("Recipient", list(usr_dict.keys()))
        msg = st.text_area("Message")
        if st.button("Send", type="primary"):
            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (usr_dict[target], msg))
            st.success("Sent!")

# ==========================================
# 6. APP EXECUTION
# ==========================================
def main():
    init_db()
    if not st.session_state.user_id:
        render_auth()
    else:
        page = st.session_state.current_page
        u_id = st.session_state.user_id
        
        if page == 'Home': render_home(u_id)
        elif page == 'Accounts': render_accounts(u_id)
        elif page == 'Transactions': render_transactions(u_id)
        elif page == 'Notifications': render_notifications(u_id)
        elif page == 'Settings': render_settings(u_id)
        elif page == 'Admin' and st.session_state.role == 'admin': render_admin()

if __name__ == "__main__":
    main()
