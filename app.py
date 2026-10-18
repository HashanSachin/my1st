import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import plotly.express as px
import hashlib
import uuid
from datetime import datetime

# ==========================================
# 1. APP CONFIGURATION & PREMIUM CSS
# ==========================================
st.set_page_config(page_title="FinMaster Pro", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Super App Clean Theme */
    .stApp { background-color: #F4F7F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    #MainMenu, footer, header, [data-testid="collapsedControl"] {visibility: hidden; display: none;}
    
    /* Modern Glassmorphism Cards */
    div[data-testid="stVerticalBlock"] > div {
        background: #ffffff;
        border-radius: 20px;
        padding: 5px;
    }
    
    /* Premium Typography */
    h1, h2, h3 { color: #111827; font-weight: 700; letter-spacing: -0.5px; }
    p { color: #6B7280; }
    
    /* Fintech Action Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        border: none;
        border-radius: 16px;
        min-height: 55px;
        font-size: 16px;
        font-weight: 600;
        box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div.stButton > button:active { transform: scale(0.98); }
    div.stButton > button:hover { box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4); }
    
    /* Secondary Buttons (Back, Cancel) */
    button[kind="secondary"] {
        background: #F3F4F6 !important;
        color: #374151 !important;
        box-shadow: none !important;
    }
    
    /* Beautiful Metrics */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #111827 0%, #1F2937 100%);
        padding: 25px;
        border-radius: 24px;
        color: white !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
    }
    div[data-testid="metric-container"] label { color: #9CA3AF !important; }
    div[data-testid="metric-container"] div { color: #FFFFFF !important; font-size: 36px !important; }
    
    /* Dataframes & Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div { border-radius: 12px; }
    [data-testid="stDataFrame"] { border-radius: 16px; overflow: hidden; border: 1px solid #E5E7EB; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. STATE & SPEED OPTIMIZATIONS
# ==========================================
if 'user_id' not in st.session_state:
    st.session_state.update({'user_id': None, 'role': None, 'username': None, 'current_page': 'Home'})

def change_page(page_name):
    st.session_state.current_page = page_name

# CACHE RESOURCE: Re-use the database connection to stop the app from lagging on every click
@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)

def run_query(query, params=(), fetch=False, fetch_all=False, commit=True):
    try:
        conn = init_connection()
        if conn.closed:
            conn = psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch: result = cur.fetchone()
        elif fetch_all: result = cur.fetchall()
        if commit: conn.commit()
        cur.close()
        return result
    except Exception as e:
        # Silently reset connection on pooler drops
        st.cache_resource.clear()
        return None

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), st.secrets["SECRET_SALT"].encode('utf-8'), 100000).hex()

# ==========================================
# 3. SCHEMA INITIALIZATION
# ==========================================
def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) DEFAULT 'user', status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS product_keys (id SERIAL PRIMARY KEY, key_code VARCHAR(50) UNIQUE NOT NULL, is_used BOOLEAN DEFAULT FALSE, used_by VARCHAR(50));
    CREATE TABLE IF NOT EXISTS accounts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, type VARCHAR(50), balance NUMERIC DEFAULT 0.0);
    CREATE TABLE IF NOT EXISTS transactions (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE, type VARCHAR(20), amount NUMERIC, category VARCHAR(50), description TEXT, date DATE);
    CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, message TEXT, is_read BOOLEAN DEFAULT FALSE);
    """
    run_query(schema)
    if not run_query("SELECT id FROM users WHERE username = 'admin'", fetch=True, commit=False):
        run_query("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')", ('admin', hash_password('admin123')))

# ==========================================
# 4. AUTHENTICATION UI
# ==========================================
def render_auth():
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; font-size: 42px;'>FinMaster <span style='color:#2563EB;'>Pro</span></h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 2rem;'>Enterprise Wealth Management</p>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["Secure Login", "Register"])
    with t1:
        username = st.text_input("Username", key="log_user", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="log_pass", placeholder="Enter your password")
        if st.button("Authenticate", type="primary", use_container_width=True):
            user = run_query("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, hash_password(password)), fetch=True)
            if user and user['status'] == 'active':
                st.session_state.update({'user_id': user['id'], 'username': user['username'], 'role': user['role'], 'current_page': 'Home'})
                st.rerun()
            else:
                st.error("Authentication failed or account suspended.")
    with t2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        prod_key = st.text_input("Product Key")
        if st.button("Create Account", type="primary", use_container_width=True):
            if new_user and new_pass and prod_key:
                if run_query("SELECT id FROM product_keys WHERE key_code = %s AND is_used = FALSE", (prod_key,), fetch=True):
                    if not run_query("SELECT id FROM users WHERE username = %s", (new_user,), fetch=True):
                        run_query("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (new_user, hash_password(new_pass)))
                        run_query("UPDATE product_keys SET is_used = TRUE, used_by = %s WHERE key_code = %s", (new_user, prod_key))
                        admin = run_query("SELECT id FROM users WHERE role = 'admin' LIMIT 1", fetch=True)
                        if admin: run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (admin['id'], f"New registration: {new_user}"))
                        st.success("Registration complete. You may log in.")
                    else: st.error("Username unavailable.")
                else: st.error("Invalid Product Key.")
            else: st.warning("All fields are required.")

# ==========================================
# 5. SUPER APP UI SCREENS
# ==========================================
def render_header(title):
    c1, c2 = st.columns([1, 4])
    with c1: st.button("❮ Back", on_click=change_page, args=('Home',), use_container_width=True)
    with c2: st.markdown(f"<h3 style='margin-top: 10px;'>{title}</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

def render_home(u_id):
    c1, c2 = st.columns([3, 1])
    with c1: st.markdown(f"<h2>Welcome back, <br><span style='color:#2563EB;'>{st.session_state.username}</span></h2>", unsafe_allow_html=True)
    with c2:
        unread = run_query("SELECT COUNT(*) as c FROM notifications WHERE (user_id = %s OR user_id IS NULL) AND is_read = FALSE", (u_id,), fetch=True)
        if unread and unread['c'] > 0: st.error(f"🔔 {unread['c']}")
    
    # Portfolio Balance
    accounts = run_query("SELECT name, balance FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    total_balance = sum(a['balance'] for a in accounts) if accounts else 0.0
    st.metric("Total Portfolio Value", f"${total_balance:,.2f}")
    
    # Quick Analytics Chart
    if accounts and total_balance > 0:
        df = pd.DataFrame(accounts)
        fig = px.pie(df, values='balance', names='name', hole=0.75, color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        fig.add_annotation(text="Assets", x=0.5, y=0.5, font_size=20, showarrow=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown("### Quick Actions")
    g1, g2 = st.columns(2)
    with g1:
        st.button("💳 Accounts", on_click=change_page, args=('Accounts',), use_container_width=True)
        st.button("🔔 Alerts", on_click=change_page, args=('Notifications',), use_container_width=True)
    with g2:
        st.button("🔁 Transfer", on_click=change_page, args=('Transactions',), use_container_width=True)
        st.button("⚙️ Settings", on_click=change_page, args=('Settings',), use_container_width=True)
        
    if st.session_state.role == 'admin':
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🛡️ Security & Admin", on_click=change_page, args=('Admin',), type="primary", use_container_width=True)

def render_accounts(u_id):
    render_header("My Accounts")
    
    with st.expander("➕ Open New Account", expanded=True):
        a_name = st.text_input("Account Alias")
        a_type = st.selectbox("Asset Class", ["Fiat Bank", "Investment", "Cash Reserve", "Digital/Crypto"])
        a_bal = st.number_input("Initial Deposit ($)", value=0.0)
        if st.button("Initialize Account", type="primary", use_container_width=True):
            run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s)", (u_id, a_name, a_type, a_bal))
            st.rerun()

    st.markdown("### Active Assets")
    accounts = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id = %s ORDER BY balance DESC", (u_id,), fetch_all=True)
    if accounts:
        for acc in accounts:
            st.markdown(f"<div style='padding: 15px; background: white; border-radius: 12px; border: 1px solid #E5E7EB; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<div><strong style='font-size:18px;'>{acc['name']}</strong><br><small style='color:gray;'>{acc['type']}</small></div>"
                        f"<div style='font-size:18px; font-weight:bold; color:#111827;'>${acc['balance']:,.2f}</div></div>", unsafe_allow_html=True)
            if st.button(f"Close {acc['name']}", key=f"del_{acc['id']}", type="secondary", use_container_width=True):
                run_query("DELETE FROM accounts WHERE id = %s", (acc['id'],))
                st.rerun()

def render_transactions(u_id):
    render_header("Global Transfers")
    
    accounts = run_query("SELECT id, name FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    if not accounts:
        st.warning("Initialize an account before routing funds.")
        return

    acc_dict = {a['name']: a['id'] for a in accounts}
    
    with st.expander("💸 Execute Transaction", expanded=True):
        t_acc = st.selectbox("Funding Source", list(acc_dict.keys()))
        t_type = st.selectbox("Direction", ["Income (Deposit)", "Expense (Withdrawal)"])
        t_amt = st.number_input("Volume", min_value=0.01)
        t_cat = st.text_input("Category Tag")
        t_date = st.date_input("Execution Date")
        if st.button("Process Transfer", type="primary", use_container_width=True):
            acc_id = acc_dict[t_acc]
            type_val = "Income" if "Income" in t_type else "Expense"
            run_query("INSERT INTO transactions (user_id, account_id, type, amount, category, date) VALUES (%s, %s, %s, %s, %s, %s)",
                      (u_id, acc_id, type_val, t_amt, t_cat, t_date))
            mod = t_amt if type_val == 'Income' else -t_amt
            run_query("UPDATE accounts SET balance = balance + %s WHERE id = %s", (mod, acc_id))
            st.rerun()

    txns = run_query("SELECT t.id, a.name as acc, t.date, t.type, t.amount, t.category FROM transactions t JOIN accounts a ON t.account_id = a.id WHERE t.user_id = %s ORDER BY t.date DESC LIMIT 50", (u_id,), fetch_all=True)
    if txns:
        st.markdown("### Ledger History")
        t_id = st.selectbox("Select Ledger Entry to Edit/Void", [t['id'] for t in txns], format_func=lambda x: f"{next(t['date'] for t in txns if t['id']==x)} | ${next(t['amount'] for t in txns if t['id']==x)}")
        curr = next(t for t in txns if t['id'] == t_id)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Void Record", type="secondary", use_container_width=True):
                run_query("DELETE FROM transactions WHERE id=%s", (t_id,))
                st.rerun()
        with c2:
            e_amt = st.number_input("Adjust Volume", value=float(curr['amount']), key="e_a")
            if st.button("Confirm Edit", type="primary", use_container_width=True):
                run_query("UPDATE transactions SET amount=%s WHERE id=%s", (e_amt, t_id))
                st.rerun()

def render_settings(u_id):
    render_header("Security Profile")
    st.markdown("**Identity Management**")
    new_u = st.text_input("New Identity Alias")
    if st.button("Update Alias", type="primary", use_container_width=True):
        if run_query("SELECT id FROM users WHERE username = %s", (new_u,), fetch=True): st.error("Alias unavailable.")
        else:
            run_query("UPDATE users SET username = %s WHERE id = %s", (new_u, u_id))
            st.session_state.username = new_u
            st.success("Identity Updated.")
            
    st.markdown("<br>**Cryptographic Key Update**", unsafe_allow_html=True)
    new_p = st.text_input("New Secure Password", type="password")
    if st.button("Update Keys", type="primary", use_container_width=True):
        run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_p), u_id))
        st.success("Key Updated.")

def render_notifications(u_id):
    render_header("System Alerts")
    notifs = run_query("SELECT * FROM notifications WHERE user_id = %s OR user_id IS NULL ORDER BY id DESC", (u_id,), fetch_all=True)
    
    if notifs:
        if st.button("Acknowledge All", type="primary", use_container_width=True):
            run_query("UPDATE notifications SET is_read = TRUE WHERE user_id = %s OR user_id IS NULL", (u_id,))
            st.rerun()
        for n in notifs:
            icon, color = ("🔵", "#111827") if not n['is_read'] else ("✔️", "gray")
            st.markdown(f"<div style='padding:15px; border-bottom:1px solid #E5E7EB;'>"
                        f"<strong>{icon} Alert</strong><br><span style='color:{color};'>{n['message']}</span></div>", unsafe_allow_html=True)
    else: st.info("No active alerts.")

def render_admin():
    render_header("Command Center")
    with st.expander("🔑 Provision Registration Keys", expanded=True):
        if st.button("Generate License Key", type="primary", use_container_width=True):
            new_key = "KEY-" + str(uuid.uuid4()).split('-')[0].upper()
            run_query("INSERT INTO product_keys (key_code) VALUES (%s)", (new_key,))
            st.success(f"License Generated: {new_key}")
        keys = run_query("SELECT key_code, is_used FROM product_keys ORDER BY id DESC LIMIT 10", fetch_all=True)
        if keys: st.dataframe(pd.DataFrame(keys), use_container_width=True)

    with st.expander("👤 Network Terminations"):
        users = run_query("SELECT id, username, role FROM users", fetch_all=True)
        df_u = pd.DataFrame(users)
        st.dataframe(df_u, use_container_width=True)
        del_id = st.selectbox("Target ID", df_u[df_u['role'] != 'admin']['id'].tolist())
        if st.button("Terminate Entity", type="secondary", use_container_width=True):
            run_query("DELETE FROM users WHERE id = %s", (del_id,))
            st.rerun()

    with st.expander("📢 Global Broadcasts"):
        usr_dict = {"Global (All Nodes)": None}
        for u in users: usr_dict[f"{u['username']} (ID:{u['id']})"] = u['id']
        target = st.selectbox("Target Node", list(usr_dict.keys()))
        msg = st.text_area("Payload")
        if st.button("Deploy Broadcast", type="primary", use_container_width=True):
            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (usr_dict[target], msg))
            st.success("Deployed.")

# ==========================================
# 6. APP EXECUTION
# ==========================================
def main():
    init_db()
    if not st.session_state.user_id: render_auth()
    else:
        page = st.session_state.current_page
        if page == 'Home': render_home(st.session_state.user_id)
        elif page == 'Accounts': render_accounts(st.session_state.user_id)
        elif page == 'Transactions': render_transactions(st.session_state.user_id)
        elif page == 'Notifications': render_notifications(st.session_state.user_id)
        elif page == 'Settings': render_settings(st.session_state.user_id)
        elif page == 'Admin' and st.session_state.role == 'admin': render_admin()

if __name__ == "__main__": main()
