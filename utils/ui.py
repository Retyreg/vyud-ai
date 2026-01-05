import streamlit as st

def set_page_styling():
    """
    Injects custom CSS to override Streamlit default styles.
    Targeting: Fonts, Buttons, Charts.
    """
    st.markdown("""
        <style>
        /* IMPORT FONTS */
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&family=JetBrains+Mono&display=swap');

        /* GLOBAL TEXT STYLES */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #FAFAFA;
        }

        /* HEADINGS - Space Grotesk for Tech Vibe */
        h1, h2, h3 {
            font-family: 'Space Grotesk', sans-serif!important;
            letter-spacing: -0.03em;
            background: -webkit-linear-gradient(0deg, #FAFAFA, #00D4FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }

        /* CODE BLOCKS - JetBrains Mono */
        code,.stCodeBlock {
            font-family: 'JetBrains Mono', monospace!important;
        }

        /* BUTTONS - Neon Glow Effect */
        div.stButton > button:first-child {
            background-color: transparent;
            border: 1px solid #00D4FF;
            color: #00D4FF;
            border-radius: 8px;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        div.stButton > button:first-child:hover {
            background-color: rgba(0, 212, 255, 0.1);
            border-color: #00D4FF;
            color: #FFFFFF;
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.6); /* Neon Glow */
            transform: translateY(-2px);
        }

        /* HIDE DEFAULT STREAMLIT ELEMENTS (Optional) */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;} /* Top colored bar */
        
        /* CARD STYLE FOR METRICS */
        div[data-testid="metric-container"] {
            background-color: #262730;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #363945;
        }
        </style>
    """, unsafe_allow_html=True)