import hashlib
import json
import os
import urllib.parse
import pandas as pd
import streamlit as st
import stripe
import yfinance as yf
import pytz
import sqlite3
from datetime import datetime, timezone

# ==========================================
# 1. INITIALISATION BDD & FONCTIONS FAVORIS
# ==========================================
def init_db():
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            added_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_favorite(ticker):
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        cursor.execute(
            "INSERT INTO watchlist (ticker, added_date) VALUES (?, ?)",
            (ticker.upper(), today_str)
        )
        conn.commit()
        st.toast(f"⭐ {ticker.upper()} ajouté aux favoris !", icon="⭐")
    except sqlite3.IntegrityError:
        st.toast(f"⚠️ {ticker.upper()} est déjà dans vos favoris.", icon="⚠️")
    finally:
        conn.close()

init_db()
# ==========================================
# 1. INITIALISATION BDD & FONCTIONS FAVORIS
# ==========================================
def init_db():
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            added_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_favorite(ticker):
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        cursor.execute(
            "INSERT INTO watchlist (ticker, added_date) VALUES (?, ?)",
            (ticker.upper(), today_str)
        )
        conn.commit()
        st.toast(f"⭐ {ticker.upper()} ajouté aux favoris !", icon="⭐")
    except sqlite3.IntegrityError:
        st.toast(f"⚠️ {ticker.upper()} est déjà dans vos favoris.", icon="⚠️")
    finally:
        conn.close()

# On initialise la table SQLite dès le chargement de la page
init_db()
# ==========================================
# 1. CONFIGURATION STRIPE & SECRETS
# ==========================================
# Récupération de la clé Stripe (depuis st.secrets ou fallback pour le test local)
raw_key = str(st.secrets.get("STRIPE_SECRET_KEY", ""))
clean_key = raw_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")
stripe.api_key = clean_key
# URL de ton site (mise à jour automatiquement sur Streamlit Cloud)
APP_URL = st.secrets.get("APP_URL", "http://localhost:8501")

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES (JSON)
# ==========================================
DB_FILE = "users_db.json"


def load_users():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ==========================================
# 3. FONCTIONS INTÉGRATION STRIPE
# ==========================================
def create_stripe_checkout_session(user_email):
    """Génère une page de paiement Stripe pour l'abonnement à 9.99$/mois"""
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=user_email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Abonnement IA Bourse Pro",
                        "description": (
                            "Accès illimité aux analyses IA, signaux"
                            " d'arbitrage et alertes."
                        ),
                    },
                    "unit_amount": 999,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{APP_URL}/?payment=success&email="
            + urllib.parse.quote(user_email),
            cancel_url=f"{APP_URL}/?payment=cancel",
        )
        return checkout_session.url
    except Exception as e:
        st.error(f"Erreur de communication avec Stripe : {e}")
        return None

# ==========================================
# 4. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(
    page_title="IA StockAdvisor Pro", page_icon="📈", layout="wide"
)

# Gestion du retour de paiement Stripe via les paramètres d'URL
query_params = st.query_params
if query_params.get("payment") == "success":
    user_to_upgrade = query_params.get("email")
    if user_to_upgrade:
        users = load_users()
        if user_to_upgrade in users:
            users[user_to_upgrade]["is_pro"] = True
            save_users(users)
            st.success(
                "🎉 Paiement réussi ! Votre compte a été mis à niveau en"
                " version PRO."
            )

# Initialisation de la session utilisateur
if "user" not in st.session_state:
    st.session_state["user"] = None

# ==========================================
# 5. BARRE LATÉRALE : AUTHENTIFICATION & COMPTE
# ==========================================
st.sidebar.title("📈 StockAdvisor IA")

users = load_users()

if st.session_state["user"] is None:
    st.sidebar.subheader("Connexion / Inscription")
    menu = st.sidebar.radio("Option", ["Se connecter", "Créer un compte"])

    email_input = st.sidebar.text_input("Adresse E-mail").lower().strip()
    password_input = st.sidebar.text_input("Mot de passe", type="password")

    if menu == "Créer un compte":
        if st.sidebar.button("S'inscrire"):
            if email_input in users:
                st.sidebar.error("Un compte existe déjà avec cet email.")
            elif email_input and password_input:
                users[email_input] = {
                    "password": hash_password(password_input),
                    "is_pro": False,
                }
                save_users(users)
                st.sidebar.success("Compte créé ! Connectez-vous.")
            else:
                st.sidebar.warning("Veuillez remplir tous les champs.")

    elif menu == "Se connecter":
        if st.sidebar.button("Connexion"):
            if email_input in users and users[email_input][
                "password"
            ] == hash_password(password_input):
                st.session_state["user"] = email_input
                st.rerun()
            else:
                st.sidebar.error("E-mail ou mot de passe incorrect.")
else:
    current_email = st.session_state["user"]
    is_pro = users.get(current_email, {}).get("is_pro", False)

    st.sidebar.write(f"👤 Connecté : **{current_email}**")
    st.sidebar.write(
        f"Statut : **{'🟢 membre PRO' if is_pro else '⚪ Compte Gratuit'}**"
    )

    # Code Promo / Pass Propriétaire pour tester gratuitement
    if not is_pro:
        promo_code = st.sidebar.text_input("Code Promo / Admin", type="password")
        if promo_code in ["OWNER100", "ADMIN2026"]:
            users[current_email]["is_pro"] = True
            save_users(users)
            st.sidebar.success("Accès Administrateur Débloqué !")
            st.rerun()

    if st.sidebar.button("Déconnexion"):
        st.session_state["user"] = None
        st.rerun()

# ==========================================
# 6. APPLICATION PRINCIPALE
# ==========================================
current_user = st.session_state["user"]
user_is_pro = (
    users.get(current_user, {}).get("is_pro", False) if current_user else False
)

st.title("🤖 IA Conseiller & Suivi Boursier")

# Bannière de vente pour la version Pro
if not user_is_pro:
    st.info(
        "💡 **Version Gratuite :** Analyse restreinte à l'action d'exemple"
        " (AAPL). Passez à la **version PRO (9.99 $/mois)** pour suivre"
        " n'importe quelle entreprise, recevoir des signaux d'arbitrage (Quand"
        " vendre X pour acheter Y) et débloquer les alertes IA."
    )

    if current_user:
        if st.button("🚀 Passer à la version PRO (9.99 $/mois) via Stripe"):
            checkout_url = create_stripe_checkout_session(current_user)
            if checkout_url:
                st.markdown(
                    f"[👉 Cliquez ici pour régler sur la page sécurisée Stripe]({checkout_url})"
                )
    else:
        st.warning("Veuillez créer un compte et vous connecter pour vous abonner.")

st.markdown("---")

# Sélection de l'action à analyser
if user_is_pro:
    ticker_input = st.text_input(
        "🔍 Entrez le symbole d'une action (ex: NVDA, TSLA, MC.PA, MSFT) :",
        "NVDA",
    )
else:
    ticker_input = "AAPL"
    st.write("📌 **Action en démonstration (Gratuit) :** AAPL (Apple Inc.)")

# Récupération des données yfinance
@st.cache_data(ttl=3600)
def fetch_stock_data(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d")
        return df
    except Exception:
        return None


data = fetch_stock_data(ticker_input)

if data is not None and not data.empty:
    # Nettoyage des colonnes si multi-index
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Calcul d'indicateurs simples (Moyennes Mobiles)
    data["MA50"] = data["Close"].rolling(window=50).mean()
    data["MA200"] = data["Close"].rolling(window=200).mean()

# 1. Détection de la devise dynamique
    if ticker_input.endswith(".MA"):
        currency = "DH"
    elif ticker_input.endswith(".DE") or ticker_input.endswith(".PA"):
        currency = "€"
    else:
        currency = "$"

   # 2. Statut du marché et compte à rebours (sans pytz)
try:
    now_utc = datetime.now(timezone.utc)
    # Sélection des horaires selon le marché
    if ticker_input.endswith(".DE") or ticker_input.endswith(".PA"):
        # Bourses européennes (UTC+2 en heure d'été) : 07:00 UTC à 15:30 UTC
        open_hour, close_hour = 7, 15
        close_minute = 30
        tz_label = "Europe/Paris/Berlin"
    else:
        # US (UTC-4 en heure d'été) : 13:30 UTC à 20:00 UTC
        open_hour, close_hour = 13, 20
        close_minute = 0
        tz_label = "US/Eastern"

    is_weekend = now_utc.weekday() >= 5

    open_time = now_utc.replace(hour=open_hour, minute=30 if open_hour == 13 else 0, second=0, microsecond=0)
    close_time = now_utc.replace(hour=open_hour, minute=close_minute, second=0, microsecond=0)

    is_open = (not is_weekend) and (open_time <= now_utc <= close_time)

if is_open:
        st.success(f"🟢 **Marché Ouvert** ({tz_label})")
    else:
        next_open = open_time
        if now_utc > close_time:
            next_open += timedelta(days=1)
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        
            diff = next_open - now_utc
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            st.warning(f"🔴 **Marché Fermé** | Ouvre dans {diff.days * 24 + hours}h {minutes}min")
except Exception as e:
    st.info(f"Erreur marché : {e}")
    # 3. Récupération du prix en direct
    try:
        last_price = float(ticker.fast_info['lastPrice'])
    except:
        last_price = float(data["Close"].dropna().iloc[-1])
    last_ma50 = float(data["MA50"].dropna().iloc[-1])
    last_ma200 = float(data["MA200"].dropna().iloc[-1])

    col1, col2, col3 = st.columns(3)
    col1.metric("Prix Actuel", f"{last_price:.2f} {currency}")
    col2.metric("Moyenne Mobile 50j", f"{last_ma50:.2f} {currency}")
    col3.metric("Moyenne Mobile 200j", f"{last_ma200:.2f} {currency}")

    # Graphique
  # Titre du graphique + Bouton Favori alignés
col_title, col_fav_btn = st.columns([3, 1])

with col_title:
    st.subheader(f"Évolution et Indicateurs : {ticker_input.upper()}")

with col_fav_btn:
    if st.button("⭐ Favori", key="btn_add_fav", use_container_width=True):
        add_favorite(ticker_input)

# Remets cette ligne TOUT À GAUCHE (sans aucun espace au début) :
st.line_chart(data[["Close", "MA50", "MA200"]])

   # Module de recommandation IA
st.subheader("🤖 Recommandation de l'Algorithme IA")

# 1. Analyse technique du ticker sélectionné
if last_price > last_ma50 and last_ma50 > last_ma200:
    signal = "🟢 ACHETER / CONSERVER"
    explanation = f"Tendances très positives pour {ticker_input.upper()} : le prix ({last_price:.2f} {currency}) est au-dessus des moyennes mobiles à 50 et 200 jours (signal haussier puissant)."
elif last_price < last_ma50 and last_ma50 < last_ma200:
    signal = "🔴 VENDRE / ALLÉGER"
    explanation = f"Tendances baissières pour {ticker_input.upper()} : le prix actuel est en dessous de ses moyennes mobiles 50j et 200j."
else:
    signal = "🟠 NEUTRE / CONSOLIDATION"
    explanation = f"Signal mitigé pour {ticker_input.upper()} : le cours évolue entre ses moyennes mobiles à 50 et 200 jours."

st.markdown(f"**Signal pour {ticker_input.upper()} :** {signal}")
st.caption(explanation)

st.markdown("---")

# 2. Suggérer 3 stratégies basées sur le capital disponible
st.subheader("💡 Suggestions d'allocation intelligente")

# Calcul du nombre d'actions entières possibles pour l'action analysée
capital = st.number_input("Capital à investir ($)", min_value=10.0, value=1000.0, step=50.0, key="capital_input")
nb_actions_entieres = int(capital // last_price) if last_price > 0 else 0

# Liste de tickers de référence selon la devise
if currency == "€":
    cheap_alt_name = "Airbus (AIR.PA)"
    premium_alt_name = "ASML (ASML.AS)"
    premium_price_est = 750.0
elif currency == "DH":
    cheap_alt_name = "Attijariwafa Bank"
    premium_alt_name = "BCP"
    premium_price_est = 300.0
else:
    cheap_alt_name = "Apple (AAPL)"
premium_alt_name = "Nvidia (NVDA)"
premium_price_est = 130.0

col_rec1, col_rec2, col_rec3 = st.columns(3)

# Option 1 : Action sélectionnée
with col_rec1:
    st.markdown("### 1. Actif Sélectionné")
    if nb_actions_entieres >= 1:
        cout_total = nb_actions_entieres * last_price
        reste = capital - cout_total
        st.success(f"**Achat direct**\n\n- **{nb_actions_entieres}** action(s) de **{ticker_input.upper()}**\n- Coût : **{cout_total:.2f} {currency}**\n- Reste : **{reste:.2f} {currency}**")
    else:
        fraction = capital / last_price if last_price > 0 else 0
        st.info(f"**Achat fractionné**\n\nLe prix ({last_price:.2f} {currency}) dépasse votre budget.\n- Vous pouvez acheter **{fraction:.2f}** action de {ticker_input.upper()}")

# Option 2 : Alternative dans le budget
with col_rec2:
    st.markdown("### 2. Option Diversification")
    st.success(f"**Achat direct**\n\n- Suggéré : **{cheap_alt_name}**\n- Accessible avec votre capital de **{capital:.0f} {currency}**.")

# Option 3 : Achat Fractionné
with col_rec3:
    st.markdown("### 3. Achat Fractionné")
    ratio_fraction = capital / premium_price_est
    st.warning(f"**Fraction d'action**\n\n- Suggéré : **{premium_alt_name}**\n- Avec votre budget, vous obtenez **{ratio_fraction:.3f}** action.\n- Idéal pour investir progressivement.")

# Module Arbitrage IA
if "ACHETER" in signal:
    score = "8.8/10"
    alt = "Titre solide (Aucune alternative requise)"
    if nb_actions_entieres > 0:
        conseil = f"Acheter environ {nb_actions_entieres} action(s) de {ticker_input.upper()} avec vos {capital}$."
    else:
        conseil = f"Votre budget ({capital}$) est inférieur au prix d'une action ({last_price:.2f}$). Utilisez les fractions d'actions."

elif "VENDRE" in signal:
    score = "3.5/10"
    alt = "NVDA" if ticker_input.upper() != "NVDA" else "MSFT"
    montant_arbitrage = round(capital * 0.5, 2)
    conseil = f"Alléger la position et réallouer {montant_arbitrage}$ vers {alt}."

else:
    score = "5.5/10"
    alt = "SPY (Indice S&P 500)"
    conseil = f"Garder vos {capital}$ en liquidités en attente d'un signal plus clair."

st.json({
    "Action analysée": ticker_input.upper(),
    "Score de croissance IA": score,
    "Alternative suggérée (Plus fort momentum)": alt,
    "Conseil d'arbitrage": conseil
})

# Avertissement Légal / Disclaimer
st.markdown("---")
st.caption(
    "⚠️ **Avertissement de responsabilité** : L'IA Kouhen FinTech et les signaux d'analyse fournis "
    "sur cette application sont transmis à titre purement informatif et éducatif. "
    "Ils n'incitent ni à acheter ni à vendre des instruments financiers. "
    "Les investissements sur les marchés comportent des risques de perte en capital."
)
