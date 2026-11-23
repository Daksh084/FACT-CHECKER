"""FactCheck — evidence-first PDF fact checking for marketing teams."""
from __future__ import annotations

import html
import hashlib
import ipaddress
import io
import os
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from xml.sax.saxutils import escape as xml_escape

import requests
import streamlit as st
from bs4 import BeautifulSoup
from pypdf import PdfReader
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_NAME = "FactCheck"
MAX_PDF_MB = 20
HEADERS = {"User-Agent": "FactCheck/1.0 (+https://factcheck.app; evidence research)"}

st.set_page_config(page_title="FactCheck · Truth layer", page_icon="⌕", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');
:root{--ink:#17243a;--muted:#748197;--line:#e5eaf1;--green:#087e72;--mint:#e8f7f2;--navy:#101c31;--paper:#f5f7fb;--purple:#7168e8}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp{background:radial-gradient(ellipse at 87% 0%,#e9efff 0,transparent 33%),var(--paper)}
.block-container{max-width:1320px;padding:1.5rem 2rem 4rem}
h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.04em;color:var(--ink)}
h2{font-size:1.45rem!important} h3{font-size:1.1rem!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#121f35,#182842);border-right:1px solid #263850}
[data-testid="stSidebar"] *{color:#e5edf8!important}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#b7c6d9!important}
.eyebrow{font:500 10px 'DM Mono';letter-spacing:.16em;color:#68d4bb;text-transform:uppercase}
.hero{position:relative;overflow:hidden;background:radial-gradient(ellipse at 84% 12%,rgba(106,104,232,.44),transparent 36%),linear-gradient(118deg,#13233c,#172b45 58%,#194a4d);border:1px solid #283b56;border-radius:25px;padding:34px 38px;margin:8px 0 23px;box-shadow:0 18px 48px rgba(22,37,61,.15)}
.hero:after{content:' ';position:absolute;width:290px;height:290px;border:1px solid rgba(127,230,206,.17);border-radius:50%;right:8%;top:23%;box-shadow:0 0 0 28px rgba(127,230,206,.035),0 0 0 64px rgba(127,230,206,.025)}
.hero h1{color:#fff;font-size:clamp(29px,3.1vw,43px);margin:7px 0 9px;line-height:1.12;max-width:790px}
.hero p{color:#c1cddd;font-size:15px;line-height:1.65;margin:0;max-width:720px}
.hero-meta{position:relative;z-index:1;display:flex;gap:9px;flex-wrap:wrap;margin-top:22px}
.hero-pill{border:1px solid rgba(205,224,244,.2);background:rgba(255,255,255,.07);color:#e3ecf8;border-radius:999px;padding:7px 11px;font:11px 'DM Mono'}
.workspace-head{display:flex;justify-content:space-between;align-items:center;margin:12px 2px 16px}
.panel{background:rgba(255,255,255,.91);border:1px solid var(--line);border-radius:18px;padding:22px 24px;margin-bottom:16px;box-shadow:0 5px 18px rgba(29,51,81,.035)}
.upload-panel{background:linear-gradient(120deg,#fff,#f4fbf8);border:1px solid #d9ebe5}
.claim{background:white;border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin:12px 0;box-shadow:0 5px 18px rgba(29,51,81,.035)}
.claim{padding:20px 22px;margin:16px 0 10px;border-radius:14px;box-shadow:0 2px 8px rgba(29,51,81,.025)}
.claimline{font-size:17px!important;line-height:1.55!important;font-weight:650!important;letter-spacing:-.02em;margin:13px 0 8px!important;color:#172b45!important}
.claim .small{font-size:12px;line-height:1.6;max-width:1000px}
.filter-heading{display:flex;align-items:center;justify-content:space-between;margin:0 0 14px}
.filter-title{font:700 13px Manrope;color:#1c2e47;letter-spacing:-.01em}
.filter-count{font:10px 'DM Mono';color:#8190a4;letter-spacing:.08em;text-transform:uppercase}
div[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid #e1e7ef!important;border-radius:15px!important;background:rgba(255,255,255,.92)!important;padding:16px 18px!important;box-shadow:0 4px 14px rgba(29,51,81,.035)}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div{min-height:42px;border-radius:9px;border-color:#dfe6ef;background:#fbfcfe}
div[data-testid="stTextInput"] input{min-height:42px;border-radius:9px;border-color:#dfe6ef;background:#fbfcfe}
div[data-testid="stWidgetLabel"] p{font-size:12px!important;font-weight:600;color:#53647b;margin-bottom:5px}
div[data-baseweb="select"] div{font-size:13px!important}
div[data-testid="stTextInput"] input{font-size:13px!important}
.claimline{font-size:15px;font-weight:600;line-height:1.65;margin:12px 0;color:#23314a}
.tag{display:inline-block;border-radius:99px;padding:5px 10px;font:500 10px 'DM Mono';margin:0 6px 0 0;letter-spacing:.04em}
.verified{background:#e3f6ed;color:#176943}.inaccurate{background:#fff3da;color:#8c5a00}.false{background:#ffebe9;color:#a1362c}.unclear{background:#edf1f6;color:#536175}.reviewed{background:#eeebff;color:#584fc1}.entity{background:#edf0ff;color:#5049a4}
.evidence{border:1px solid #e3e9f0;border-left:3px solid #91a6ba;border-radius:11px;padding:14px 16px;margin:9px 0;background:#fff;color:#4a5870;font-size:13px;line-height:1.65;box-shadow:0 2px 8px rgba(29,51,81,.025)}
.evidence a{color:#087e72;text-decoration:none;font-weight:700}.evidence a:hover{text-decoration:underline}.small{font-size:12px;color:#8390a2}
.evidence-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.source-domain{font:500 10px 'DM Mono';color:#56667c;background:#f0f3f7;border-radius:6px;padding:5px 8px}
.source-title{display:block;margin:2px 0 7px;font-size:14px;line-height:1.4}
.source-excerpt{margin:0;color:#526178;font-size:13px;line-height:1.6}
.section-label{font:700 11px 'DM Mono';color:#8491a3;letter-spacing:.1em;text-transform:uppercase;margin:20px 0 8px}
div[data-testid="stFileUploader"]{background:#fff;border:1px dashed #87b9a8;border-radius:15px;padding:13px}
div.stButton>button{background:linear-gradient(100deg,#087e72,#119b85);color:white;border:0;border-radius:10px;font-weight:700;padding:.62rem 1.05rem;box-shadow:0 6px 14px rgba(8,126,114,.14)}
div.stButton>button:hover{background:#086d64;color:#fff;border:0}
[data-testid="stMetric"]{background:white;border:1px solid var(--line);padding:16px 18px;border-radius:15px;box-shadow:0 5px 18px rgba(29,51,81,.035)}
[data-testid="stMetricLabel"]{font:500 10px 'DM Mono';text-transform:uppercase;letter-spacing:.08em;color:#75839a}
[data-testid="stMetricValue"]{font-family:'Manrope';font-size:1.8rem;color:#1a2941}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.68)}
div[data-testid="stDownloadButton"] button{border:1px solid #dbe4ee;background:white;color:#1f3854;border-radius:9px;font-weight:600}
hr{border-color:#e5eaf1}
/* FUTURE INTERFACE — deep-space canvas with restrained signal colors */
:root{--ink:#e7f1ff;--muted:#92a8c2;--line:rgba(126,164,207,.2);--green:#62efd0;--mint:rgba(77,226,194,.1);--navy:#07111f;--paper:#07111f;--purple:#a89aff}
.stApp{color:#e7f1ff;background:radial-gradient(ellipse at 12% 0%,rgba(27,83,123,.26),transparent 34%),radial-gradient(ellipse at 92% 8%,rgba(58,44,125,.23),transparent 32%),linear-gradient(180deg,#07111f 0%,#0a1425 48%,#08121f 100%)}
.block-container{max-width:1440px;padding-top:1.3rem}
h1,h2,h3{color:#edf5ff;text-shadow:0 0 22px rgba(83,179,226,.12)}
p,span,label,[data-testid="stMarkdownContainer"]{color:inherit}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#081321,#0c192a 70%,#0b1726);border-right:1px solid rgba(100,178,205,.2);box-shadow:8px 0 36px rgba(0,0,0,.2)}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong{color:#74ecd4;letter-spacing:.04em}
[data-testid="stSidebar"] hr{border-color:rgba(111,164,191,.2)}
.hero{background:radial-gradient(ellipse at 84% 10%,rgba(84,91,207,.33),transparent 36%),radial-gradient(ellipse at 65% 110%,rgba(30,163,157,.15),transparent 45%),linear-gradient(115deg,#0c1b2d,#101d34 58%,#102b35);border:1px solid rgba(105,202,214,.28);border-radius:22px;box-shadow:0 18px 60px rgba(0,0,0,.28),inset 0 1px rgba(255,255,255,.045)}
.hero:after{border-color:rgba(91,231,203,.22);box-shadow:0 0 0 28px rgba(91,231,203,.045),0 0 0 64px rgba(91,231,203,.025),0 0 80px rgba(48,210,187,.1)}
.eyebrow{color:#69efd4}.hero-pill{border-color:rgba(150,192,224,.22);background:rgba(9,20,36,.48);color:#c9dbed}
.panel,.claim,div[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(145deg,rgba(18,33,53,.92),rgba(12,25,42,.94))!important;border-color:rgba(119,157,192,.2)!important;color:#e2edfa;box-shadow:0 12px 34px rgba(0,0,0,.17),inset 0 1px rgba(255,255,255,.035)}
.upload-panel{background:linear-gradient(120deg,rgba(15,36,53,.96),rgba(12,43,47,.88))!important;border-color:rgba(82,226,191,.23)!important}
.claim{border-radius:15px;border-left:2px solid rgba(88,228,196,.55)!important}
.claimline{color:#eff6ff!important}
.filter-title{color:#e5f0fe}.filter-count,.small{color:#93a8c0}.section-label{color:#6fe6d0}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div,div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea{background:#0b1929!important;color:#e5f0fe!important;border:1px solid rgba(124,168,202,.25)!important;border-radius:10px!important}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div:focus-within,div[data-testid="stTextInput"] input:focus,div[data-testid="stTextArea"] textarea:focus{border-color:#55d9c5!important;box-shadow:0 0 0 2px rgba(85,217,197,.12)!important}
div[data-testid="stWidgetLabel"] p{color:#aec2d8!important}
div[data-baseweb="popover"]{background:#102036!important;border:1px solid rgba(112,166,202,.28)!important}
div[data-baseweb="popover"] *{color:#dceaff!important}
.tag{border:1px solid rgba(152,181,210,.12)}
.verified{background:rgba(48,210,151,.13);color:#6ef0bc;border-color:rgba(91,237,179,.25)}
.inaccurate{background:rgba(255,181,72,.13);color:#ffd07b;border-color:rgba(255,195,92,.23)}
.false{background:rgba(255,104,119,.13);color:#ff9aa5;border-color:rgba(255,118,133,.23)}
.unclear{background:rgba(123,154,188,.13);color:#b5c8dd;border-color:rgba(141,171,202,.16)}
.reviewed,.entity{background:rgba(150,130,255,.14);color:#c6baff;border-color:rgba(173,154,255,.2)}
.evidence{background:linear-gradient(145deg,rgba(15,30,49,.94),rgba(12,25,42,.96));border-color:rgba(123,164,195,.19);border-left-color:#3bcbb5;color:#c0d0e2;box-shadow:0 8px 22px rgba(0,0,0,.12)}
.source-domain{background:rgba(127,160,190,.11);color:#bad0e5;border:1px solid rgba(126,164,196,.13)}
.source-title,.evidence a{color:#63e4d0!important}.source-excerpt{color:#aec2d8}
div[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(18,35,56,.96),rgba(11,24,41,.96));border:1px solid rgba(112,160,198,.2);box-shadow:0 10px 28px rgba(0,0,0,.16)}
[data-testid="stMetricLabel"]{color:#91aac3}[data-testid="stMetricValue"]{color:#ebf4ff}
div[data-testid="stExpander"]{border:1px solid rgba(120,163,196,.22);border-radius:13px;background:rgba(12,26,43,.78);color:#dceaff}
div[data-testid="stExpander"] summary{color:#dceaff}
div[data-testid="stFileUploader"]{background:rgba(10,25,41,.86);border:1px dashed rgba(86,222,194,.52);border-radius:16px}
div[data-testid="stFileUploader"] section{background:rgba(16,36,54,.55);border-radius:12px}
div.stButton>button{background:linear-gradient(100deg,#087f80,#18b99b);color:#f4fffd;border:1px solid rgba(103,242,211,.32);border-radius:10px;box-shadow:0 7px 22px rgba(14,180,157,.18);transition:transform .15s,box-shadow .15s}
div.stButton>button:hover{background:linear-gradient(100deg,#09918e,#23c7a7);transform:translateY(-1px);box-shadow:0 10px 28px rgba(14,210,177,.25)}
div[data-testid="stDownloadButton"] button{background:rgba(21,43,64,.9);border:1px solid rgba(114,171,202,.27);color:#d8e8f7}
div[data-testid="stDataFrame"]{border:1px solid rgba(112,160,198,.2);border-radius:12px;overflow:hidden}
hr{border-color:rgba(115,158,191,.18)}
@media (prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important}}
/* Contrast pass: explicitly style Streamlit's generated text and controls. */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{color:#eaf2ff!important}
.stApp p,.stApp li,.stApp label,.stApp [data-testid="stMarkdownContainer"] p,.stApp [data-testid="stCaptionContainer"] p{color:#c6d5e7}
.stApp [data-testid="stCaptionContainer"] p{color:#9fb2c8}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{color:#f1f6ff!important}
.stApp [data-testid="stWidgetLabel"] p,.stApp label p{color:#c3d3e6!important}
.stApp input,.stApp textarea,[data-baseweb="select"] input{color:#f2f7ff!important;-webkit-text-fill-color:#f2f7ff!important;caret-color:#65ead0!important}
.stApp input::placeholder,.stApp textarea::placeholder{color:#91a7bf!important;-webkit-text-fill-color:#91a7bf!important;opacity:1}
.stApp [data-baseweb="select"] span,.stApp [data-baseweb="select"] div{color:#e7f0fc}
[data-baseweb="menu"],[data-baseweb="popover"] ul{background:#102036!important}
[data-baseweb="menu"] li,[data-baseweb="menu"] li *{color:#e8f1fc!important}
[data-baseweb="menu"] li[aria-selected="true"]{background:#17403f!important}
.stApp [data-testid="stRadio"] label,.stApp [data-testid="stCheckbox"] label{color:#d6e3f2!important}
.stApp [data-testid="stExpander"] summary,.stApp [data-testid="stExpander"] summary p{color:#e5effc!important}
.stApp [data-testid="stDataFrame"] *, .stApp [data-testid="stTable"] *{color:#dbe8f7}
.stApp [data-testid="stMetricLabel"] div{color:#a9bed3!important}
.stApp [data-testid="stMetricValue"] div{color:#f1f6ff!important}
.stApp [data-testid="stFileUploader"] section,.stApp [data-testid="stFileUploader"] section *{color:#d8e7f7!important}
.stApp [data-testid="stFileUploader"] button{background:#18334a!important;color:#f1f7ff!important;border:1px solid rgba(129,184,213,.35)!important}
.stApp [data-testid="stAlert"] p,.stApp [data-testid="stAlert"] li{color:#f1f6ff!important}
.stApp [data-testid="stAlert"]{background:#14243a!important;border:1px solid rgba(131,170,205,.3)!important}
.stApp a{color:#69e7d2}
.stApp .hero p,.stApp .hero h1,.stApp .hero .hero-pill,.stApp .hero .eyebrow{color:inherit}
.stApp .claim .small,.stApp .source-excerpt,.stApp .evidence{color:#c4d3e4!important}
.stApp .filter-count,.stApp .small{color:#a7bad0!important}
/* Blend Streamlit's fixed toolbar into the canvas and remove excess top gap. */
header[data-testid="stHeader"]{background:#07111f!important;border:0!important;box-shadow:none!important;height:2.5rem!important}
header[data-testid="stHeader"] [data-testid="stToolbar"]{background:transparent!important}
[data-testid="stAppViewContainer"]>.main{background:transparent!important}
.block-container{padding-top:.55rem!important}
/* Premium navy + electric blue visual system */
:root{--ink:#e9f1ff;--muted:#9aabc3;--line:rgba(137,160,199,.18);--blue:#5d9dff;--cyan:#55e2ed;--purple:#a58bff;--navy:#080b13;--paper:#080b13}
html,body,[class*="css"],button,input,textarea{font-family:'Inter',ui-sans-serif,system-ui,sans-serif!important}
.stApp{background:radial-gradient(ellipse at 12% 0%,rgba(44,100,181,.18),transparent 32%),radial-gradient(ellipse at 92% 8%,rgba(108,75,196,.16),transparent 30%),linear-gradient(145deg,#080b13,#0b101b 54%,#090d17)!important}
.stApp:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;background-image:linear-gradient(rgba(137,172,224,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(137,172,224,.025) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,black,transparent 76%)}
[data-testid="stMain"]{position:relative;z-index:1}
header[data-testid="stHeader"]{background:rgba(8,11,19,.82)!important;backdrop-filter:blur(18px);border-bottom:1px solid rgba(133,158,198,.1)!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(10,15,25,.98),rgba(13,19,32,.97))!important;border-right:1px solid rgba(117,155,208,.16)!important;backdrop-filter:blur(24px)}
.hero{background:radial-gradient(ellipse at 82% 12%,rgba(92,102,222,.3),transparent 34%),radial-gradient(ellipse at 68% 105%,rgba(47,180,211,.15),transparent 45%),linear-gradient(120deg,rgba(15,23,41,.96),rgba(14,22,40,.84) 56%,rgba(17,30,53,.91))!important;border:1px solid rgba(113,157,223,.25)!important;border-radius:24px!important;box-shadow:0 24px 70px rgba(0,0,0,.36),inset 0 1px rgba(255,255,255,.07)!important;backdrop-filter:blur(18px)}
.hero:after{border-color:rgba(89,205,239,.22)!important;box-shadow:0 0 0 30px rgba(93,157,255,.045),0 0 0 68px rgba(165,139,255,.035),0 0 95px rgba(70,173,243,.12)!important}
.eyebrow,.section-label{color:#72dff4!important}.hero-pill{border-color:rgba(134,170,223,.22)!important;background:rgba(7,12,23,.48)!important}
.panel,.claim,div[data-testid="stVerticalBlockBorderWrapper"],div[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(21,29,46,.76),rgba(13,20,34,.78))!important;border:1px solid rgba(133,158,198,.17)!important;border-radius:17px!important;box-shadow:0 14px 38px rgba(0,0,0,.2),inset 0 1px rgba(255,255,255,.045)!important;backdrop-filter:blur(18px)}
.upload-panel{background:linear-gradient(120deg,rgba(18,31,51,.88),rgba(17,30,45,.83))!important;border-color:rgba(76,195,224,.26)!important}
.claim{border-left:2px solid rgba(86,177,255,.64)!important;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease!important}
.claim:hover{transform:translateY(-2px);border-color:rgba(95,169,255,.4)!important;box-shadow:0 18px 44px rgba(0,0,0,.26),0 0 22px rgba(73,148,255,.06)!important}
.evidence{background:linear-gradient(145deg,rgba(22,31,49,.81),rgba(14,22,37,.82))!important;border:1px solid rgba(122,151,190,.16)!important;border-left:3px solid #55cde8!important;border-radius:13px!important;backdrop-filter:blur(14px);transition:transform .18s ease,border-color .18s ease}
.evidence:hover{transform:translateY(-1px);border-color:rgba(85,205,232,.32)!important}
.source-title,.evidence a{color:#74dff1!important}.source-domain{background:rgba(87,138,204,.12)!important;color:#c1d5f3!important;border:1px solid rgba(115,157,214,.16)!important}
.source-excerpt,.claim .small,.small,.filter-count{color:#aabbd2!important}
.claimline{color:#f0f5ff!important}
.verified{background:rgba(47,211,157,.12)!important;color:#80ecc5!important;border-color:rgba(92,232,187,.22)!important}
.inaccurate{background:rgba(255,182,79,.12)!important;color:#ffd28d!important;border-color:rgba(255,190,93,.2)!important}
.false{background:rgba(255,102,129,.12)!important;color:#ff9eae!important;border-color:rgba(255,118,142,.2)!important}
.unclear{background:rgba(129,153,187,.12)!important;color:#bdcce0!important}
.reviewed,.entity{background:rgba(151,126,255,.14)!important;color:#c9baff!important;border-color:rgba(168,146,255,.22)!important}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div,div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea{background:rgba(8,14,25,.78)!important;border:1px solid rgba(129,159,206,.2)!important;border-radius:11px!important;transition:border-color .16s,box-shadow .16s!important}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div:focus-within,div[data-testid="stTextInput"] input:focus,div[data-testid="stTextArea"] textarea:focus{border-color:#569cff!important;box-shadow:0 0 0 3px rgba(86,156,255,.13)!important}
div.stButton>button{background:linear-gradient(105deg,#3478ed,#416ce5 55%,#7356dc)!important;border:1px solid rgba(127,171,255,.42)!important;border-radius:11px!important;box-shadow:0 8px 24px rgba(55,111,232,.25),inset 0 1px rgba(255,255,255,.2)!important;transition:transform .16s,filter .16s,box-shadow .16s!important}
div.stButton>button:hover{filter:brightness(1.13);transform:translateY(-1px);box-shadow:0 12px 30px rgba(55,111,232,.33)!important}
div[data-testid="stDownloadButton"] button{background:rgba(25,38,60,.8)!important;border:1px solid rgba(113,158,218,.24)!important;border-radius:11px!important;color:#dce9fb!important;transition:all .16s!important}
div[data-testid="stDownloadButton"] button:hover{border-color:rgba(86,167,255,.55)!important;color:#fff!important;transform:translateY(-1px)}
div[data-testid="stExpander"]{background:rgba(15,23,38,.68)!important;border:1px solid rgba(128,155,196,.18)!important;border-radius:14px!important;backdrop-filter:blur(14px);transition:border-color .16s ease}
div[data-testid="stExpander"]:hover{border-color:rgba(102,163,235,.35)!important}
div[data-testid="stFileUploader"]{background:rgba(11,19,32,.72)!important;border:1px dashed rgba(78,187,232,.48)!important;border-radius:16px!important;backdrop-filter:blur(12px)}
div[data-testid="stFileUploader"] button{background:rgba(25,45,73,.9)!important;border:1px solid rgba(108,163,235,.36)!important;border-radius:9px!important}
[data-testid="stMetricValue"]{color:#f2f6ff!important}[data-testid="stMetricLabel"]{color:#a8bad3!important}
@keyframes rise-in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
.hero,.panel,.claim,.evidence,[data-testid="stMetric"]{animation:rise-in .32s ease-out both}
@media (prefers-reduced-motion:reduce){.hero,.panel,.claim,.evidence,[data-testid="stMetric"]{animation:none!important}.claim,.evidence,button{transition:none!important}}
</style>
""", unsafe_allow_html=True)


@dataclass
class Claim:
    text: str
    page: int
    kind: str


def pdf_text(data: bytes) -> tuple[str, list[str]]:
    reader = PdfReader(io.BytesIO(data))
    pages = [(p.extract_text() or "") for p in reader.pages]
    return "\n".join(pages), pages


def extract_claims(pages: list[str]) -> list[Claim]:
    """Extract checkable sentence-level claims with numeric/date/finance/technical signals."""
    out: list[Claim] = []
    seen: set[str] = set()
    numeric_or_date = re.compile(
        r"(?:"
        r"(?:[$€£₹]\s?\d[\d,.]*(?:\s?(?:k|m|bn|mn|million|billion|trillion))?)|"
        r"(?:\b\d[\d,.]*\s?(?:%|percent|percentage points?|x|×|ms|milliseconds?|seconds?|secs?|minutes?|mins?|hours?|days?|weeks?|months?|years?|yr|gb|tb|mb|kb|ghz|mhz|khz|mbps|gbps|watts?|kw|mw|volts?|amps?|°c|°f|dpi|fps|rpm|users?|customers?|employees?|countries|markets|requests?/s|rps)\b)|"
        r"(?:\b(?:19|20)\d{2}(?:\s?[-–/]\s?(?:19|20)?\d{2})?\b)|"
        r"(?:\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b)|"
        r"(?:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,?\s+\d{4})?\b)|"
        r"(?:\b\d+(?:\.\d+)?\s?(?:million|billion|trillion|thousand|bn|mn)\b)|"
        r"(?:\b\d+(?:\.\d+)?\b(?=\s+(?:revenue|profit|valuation|users|customers|employees|downloads|impressions|conversions|growth|decline|market share|latency|accuracy|uptime|throughput|capacity|funding|ARR|MRR|GDP|cost|price|sales|units)\b))"
        r")", re.I)
    financial_context = re.compile(r"\b(revenue|profit|cost|valuation|market cap|funding|ARR|MRR|sales|price|investment|USD|EUR|GBP)\b|[$€£₹]", re.I)
    technical_context = re.compile(r"\b(technical|latency|throughput|uptime|accuracy|precision|recall|capacity|bandwidth|API|CPU|GPU|storage|database|model size|parameters|tokens|benchmark|resolution|efficiency|temperature|power consumption|response time|error rate|availability)\b", re.I)
    date_context = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}\b|\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b", re.I)
    measurement_signal = re.compile(r"[$€£₹]|\b\d[\d,.]*\s?(?:%|percent|percentage points?|x|×|ms|milliseconds?|seconds?|minutes?|hours?|days?|weeks?|months?|years?|gb|tb|mb|kb|ghz|mhz|mbps|gbps|watts?|kw|mw|users?|customers?|employees?|requests?/s|rps)\b|\b(grew|increased|decreased|rose|fell|reached|averaged|generated|sold|processed|ranked)\b", re.I)
    for page_no, page in enumerate(pages, start=1):
        normalized = re.sub(r"(?<!\.)\n", " ", page)
        for raw in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])|\n+", normalized):
            s = re.sub(r"\s+", " ", raw).strip(" •\t\r\n")
            if len(s) < 22 or len(s) > 700 or not numeric_or_date.search(s):
                continue
            key = re.sub(r"\W+", " ", s.casefold()).strip()
            if key in seen:
                continue
            seen.add(key)
            if financial_context.search(s):
                kind = "Financial"
            elif technical_context.search(s):
                kind = "Technical"
            elif date_context.search(s) and not measurement_signal.search(s):
                kind = "Date"
            else:
                kind = "Statistic"
            out.append(Claim(s, page_no, kind))
    return out[:40]


def _unwrap_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    is_duckduckgo_redirect = (
        parsed.hostname == "duckduckgo.com"
        or (parsed.hostname or "").endswith(".duckduckgo.com")
    )
    if is_duckduckgo_redirect and parsed.path.startswith("/l/"):
        return unquote(parse_qs(parsed.query).get("uddg", [url])[0])
    return url


def _parse_duckduckgo_html(content: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    results: list[dict[str, str]] = []
    for item in soup.select(".result")[:limit]:
        anchor = item.select_one(".result__a")
        if anchor:
            snippet = item.select_one(".result__snippet")
            results.append({
                "title": anchor.get_text(" ", strip=True),
                "url": _unwrap_duckduckgo_url(anchor.get("href", "")),
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            })
    return results


def _parse_duckduckgo_lite(content: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    results: list[dict[str, str]] = []
    for anchor in soup.select(".result-link"):
        row = anchor.find_parent("tr")
        snippet_row = row.find_next_sibling("tr") if row else None
        snippet = snippet_row.select_one(".result-snippet") if snippet_row else None
        results.append({
            "title": anchor.get_text(" ", strip=True),
            "url": _unwrap_duckduckgo_url(anchor.get("href", "")),
            "snippet": snippet.get_text(" ", strip=True) if snippet else "",
        })
        if len(results) >= limit:
            break
    return results


def web_search(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Use Tavily when configured, then try both DuckDuckGo result formats."""
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not tavily_key:
        try:
            tavily_key = str(st.secrets.get("TAVILY_API_KEY", "")).strip()
        except Exception:
            pass
    if tavily_key:
        try:
            response = requests.post("https://api.tavily.com/search", json={"api_key": tavily_key, "query": query, "search_depth": "advanced", "max_results": limit, "include_answer": False}, timeout=25)
            response.raise_for_status()
            results = [{"title": x.get("title", "Source"), "url": x.get("url", ""), "snippet": x.get("content", "")} for x in response.json().get("results", [])]
            if results:
                return results[:limit]
        except requests.RequestException:
            pass
    providers = (
        ("https://html.duckduckgo.com/html/", _parse_duckduckgo_html),
        ("https://lite.duckduckgo.com/lite/", _parse_duckduckgo_lite),
    )
    for endpoint, parse_results in providers:
        try:
            response = requests.get(endpoint, params={"q": query}, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        results = parse_results(response.text, limit)
        if results:
            return results
    return []


def source_quality(url: str, claim: Claim | None = None) -> tuple[str, str]:
    """A transparent domain hint, not an endorsement of the article itself."""
    host = urlparse(url).netloc.casefold().split(":")[0].removeprefix("www.")
    if not host:
        return "Unknown domain", "unclear"
    if host.endswith((".gov", ".gov.uk", ".gov.in", ".edu", ".ac.uk")) or host in {"who.int", "un.org", "europa.eu", "worldbank.org", "imf.org", "oecd.org", "toureiffel.paris"}:
        return "Official / research domain", "verified"
    if host in {"reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "ft.com", "nature.com", "science.org", "nih.gov", "census.gov", "sec.gov"}:
        return "Established publisher", "verified"
    if claim:
        host_root = host.split(".")[-2] if "." in host else host
        if any(entity in host_root for entity in claim_entities(claim.text)):
            return "Entity-matching domain", "entity"
    return host, "unclear"


def source_access_label(source: dict[str, Any], claim: Claim) -> str:
    if source.get("page_opened"):
        return "SOURCE PAGE OPENED · TEXT CHECKED"
    if source_quality(source.get("url", ""), claim)[1] in {"verified", "entity"}:
        return "RECOGNIZED / ENTITY-MATCHING LIVE EXCERPT"
    return "SEARCH SNIPPET ONLY · NOT VERIFIED"


def fetch_source_text(url: str) -> str:
    """Fetch public article text only; reject private hosts and restrict redirects/body size."""
    try:
        current = url
        for _ in range(4):
            parsed = urlparse(current)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return ""
            host = parsed.hostname.casefold().rstrip(".")
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
                return ""
            try:
                literal = ipaddress.ip_address(host)
                if not literal.is_global:
                    return ""
            except ValueError:
                addresses = {item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
                if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                    return ""
            response = requests.get(current, headers=HEADERS, timeout=(4, 8), allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                next_url = response.headers.get("Location", "")
                response.close()
                if not next_url:
                    return ""
                current = urljoin(current, next_url)
                continue
            if response.status_code != 200 or not response.headers.get("Content-Type", "").casefold().startswith(("text/html", "application/xhtml+xml", "text/plain")):
                response.close()
                return ""
            chunks, length = [], 0
            for chunk in response.iter_content(32768):
                length += len(chunk)
                if length > 1_000_000:
                    break
                chunks.append(chunk)
            response.close()
            raw = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            if "text/plain" in response.headers.get("Content-Type", "").casefold():
                return re.sub(r"\n{3,}", "\n\n", re.sub(r"[\t ]+", " ", raw.decode(encoding, errors="replace")))[:20000]
            soup = BeautifulSoup(raw, "html.parser")
            for node in soup.select("script,style,noscript,svg,nav,footer,header,aside,form"):
                node.decompose()
            main = soup.select_one("article") or soup.select_one("main") or soup.body or soup
            page_text = main.get_text("\n", strip=True)
            page_text = re.sub(r"[\t ]+", " ", page_text)
            return re.sub(r"\n{3,}", "\n\n", page_text)[:20000]
    except Exception:
        return ""
    return ""


CLAIM_STOPWORDS = {"that", "this", "with", "from", "were", "have", "which", "their", "they", "will", "would", "about", "after", "before", "between", "more", "than", "into", "over", "under", "according", "because", "million", "billion", "percent", "year", "years", "the", "and", "for", "are", "was", "has", "had", "its", "our", "your", "than", "then", "also", "most", "each", "per", "been", "being", "can", "could", "should", "company", "report", "reported", "claim", "says", "said", "reached", "rose", "grew", "fell", "increased", "decreased", "generated", "averaged", "measured"}
NUMBER_RE = re.compile(r"(?P<currency>[$€£₹])?\s*(?P<number>\d[\d,]*(?:\.\d+)?)(?:\s*(?P<scale>trillion|billion|million|thousand|tn|bn|mn|k|m)(?![a-z]))?\s*(?P<unit>percentage points?|percent|%|milliseconds?|ms|seconds?|secs?|minutes?|mins?|hours?|days?|weeks?|months?|years?|yr|kilometers?|kilometres?|km|centimeters?|centimetres?|cm|millimeters?|millimetres?|mm|meters?|metres?|m|feet|foot|ft|inches?|miles?|mi|gbps|mbps|tb|gb|mb|kb|ghz|mhz|khz|watts?|kw|mw|volts?|amps?|fps|rpm|users?|customers?|employees?|requests?/s|rps)?(?![a-z])", re.I)


def number_signature(raw: str) -> tuple[float, str]:
    match = NUMBER_RE.search(raw)
    if not match:
        return 0.0, ""
    value = float(match.group("number").replace(",", ""))
    scale = (match.group("scale") or "").casefold()
    unit = (match.group("unit") or "").casefold()
    # "m" is commonly a million suffix while "m" after a space is the SI
    # unit meter. Prefer the unit interpretation when it is separated.
    if scale == "m" and not unit and re.search(r"\d\s+m$", raw, re.I):
        scale, unit = "", "m"
    value *= {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000, "mn": 1_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000, "tn": 1_000_000_000_000, "trillion": 1_000_000_000_000}.get(scale, 1)
    currency = match.group("currency") or ""
    if unit in {"milliseconds", "millisecond", "ms"}:
        family = "time-ms"
    elif unit in {"seconds", "second", "secs", "sec"}:
        value *= 1_000
        family = "time-ms"
    elif unit in {"minutes", "minute", "mins", "min"}:
        value *= 60_000
        family = "time-ms"
    elif unit in {"hours", "hour"}:
        value *= 3_600_000
        family = "time-ms"
    elif unit in {"meters", "meter", "metres", "metre", "m"}:
        family = "length-m"
    elif unit in {"kilometers", "kilometer", "kilometres", "kilometre", "km"}:
        value *= 1_000
        family = "length-m"
    elif unit in {"centimeters", "centimeter", "centimetres", "centimetre", "cm"}:
        value *= .01
        family = "length-m"
    elif unit in {"millimeters", "millimeter", "millimetres", "millimetre", "mm"}:
        value *= .001
        family = "length-m"
    elif unit in {"feet", "foot", "ft"}:
        value *= .3048
        family = "length-m"
    elif unit in {"inches", "inch"}:
        value *= .0254
        family = "length-m"
    elif unit in {"miles", "mile", "mi"}:
        value *= 1_609.344
        family = "length-m"
    elif unit in {"%", "percent", "percentage point", "percentage points"}:
        family = "percent"
    elif currency:
        family = "currency:" + currency
    elif unit in {"gbps", "mbps"}:
        value *= 1_000_000_000 if unit == "gbps" else 1_000_000
        family = "data-rate-bps"
    elif unit in {"tb", "gb", "mb", "kb"}:
        value *= {"tb": 1_000_000_000_000, "gb": 1_000_000_000, "mb": 1_000_000, "kb": 1_000}.get(unit, 1)
        family = "data-size-bytes"
    elif unit in {"ghz", "mhz", "khz"}:
        value *= {"ghz": 1_000_000_000, "mhz": 1_000_000, "khz": 1_000}.get(unit, 1)
        family = "frequency-hz"
    elif unit in {"watts", "watt", "kw", "mw"}:
        value *= {"kw": 1_000, "mw": 1_000_000}.get(unit, 1)
        family = "power-w"
    elif unit in {"requests/s", "rps"}:
        family = "count:requests/s"
    elif unit in {"years", "year", "yr", "months", "month", "weeks", "week", "days", "day"}:
        family = "date-unit"
    else:
        family = "count:" + unit
    return value, family


def same_numeric_family(first: str, second: str) -> bool:
    if first == second:
        return True
    return first.startswith("count:") and second.startswith("count:") and (first == "count:" or second == "count:")


def numeric_values_match(first: float, second: float) -> bool:
    # Allow small differences introduced by rounded unit conversions, e.g.
    # 330 m versus 1,083 ft, while keeping materially different values apart.
    return abs(first - second) <= max(abs(first) * 0.001, 1e-8)


def claim_terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z][a-z0-9-]{2,}", text.casefold()) if word not in CLAIM_STOPWORDS and not word.isdigit()}


ENTITY_STOPWORDS = {"the", "this", "that", "revenue", "sales", "growth", "market", "company", "product", "overall", "total", "average", "median", "annual", "monthly", "quarterly", "users", "customers", "employees", "latency", "throughput", "uptime", "accuracy", "capacity", "height", "data", "report", "research", "according", "during", "since", "from", "between", "increased", "decreased"}


def claim_entities(text: str) -> set[str]:
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9-]{2,}\b", text)
    return {candidate.casefold() for candidate in candidates if candidate.casefold() not in ENTITY_STOPWORDS}


def entity_near_number(text: str, start: int, end: int, entities: set[str], window: int = 12) -> bool:
    if not entities:
        return True
    words = [(match.group(0).casefold(), match.start(), match.end()) for match in re.finditer(r"[A-Za-z][A-Za-z0-9-]*", text)]
    before = [word for word, _, right in words if right <= start][-window:]
    after = [word for word, left, _ in words if left >= end][:window]
    near = before + after + [word for word, left, right in words if left < end and right > start]
    return bool(entities & set(near))


MONTHS = {name.casefold(): number for number, names in enumerate([("January", "Jan"), ("February", "Feb"), ("March", "Mar"), ("April", "Apr"), ("May",), ("June", "Jun"), ("July", "Jul"), ("August", "Aug"), ("September", "Sep", "Sept"), ("October", "Oct"), ("November", "Nov"), ("December", "Dec")], 1) for name in names}


def date_signatures(text: str) -> set[str]:
    dates: set[str] = set()
    for match in re.finditer(r"\b((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text):
        year, month, day = map(int, match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            dates.add(f"{year:04d}-{month:02d}-{day:02d}")
    for match in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.]((?:19|20)\d{2})\b", text):
        first, second, year = map(int, match.groups())
        if 1 <= first <= 12 and 1 <= second <= 31:
            dates.add(f"{year:04d}-{first:02d}-{second:02d}")
        if 1 <= second <= 12 and 1 <= first <= 31:
            dates.add(f"{year:04d}-{second:02d}-{first:02d}")
    month_pattern = "|".join(MONTHS)
    for match in re.finditer(rf"\b({month_pattern})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+((?:19|20)\d{{2}})\b", text, re.I):
        month, day, year = match.groups()
        dates.add(f"{int(year):04d}-{MONTHS[month.casefold()]:02d}-{int(day):02d}")
    for match in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})\.?[,]?\s+((?:19|20)\d{{2}})\b", text, re.I):
        day, month, year = match.groups()
        dates.add(f"{int(year):04d}-{MONTHS[month.casefold()]:02d}-{int(day):02d}")
    for match in re.finditer(rf"\b({month_pattern})\.?\s+((?:19|20)\d{{2}})\b", text, re.I):
        month, year = match.groups()
        dates.add(f"{int(year):04d}-{MONTHS[month.casefold()]:02d}")
    if not dates:
        dates.update(re.findall(r"\b(?:19|20)\d{2}\b", text))
    return dates


def split_evidence(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n+|(?<=[.!?])\s+|(?<=;)\s+", text) if len(part.strip()) > 30]


def focused_claim_query(claim: Claim) -> str:
    text = claim.text.casefold()
    entities = list(dict.fromkeys(claim_entities(claim.text)))
    metric_terms = {"revenue", "profit", "sales", "valuation", "market", "growth", "share", "users", "customers", "employees", "latency", "response", "time", "throughput", "uptime", "height", "tall", "length", "capacity", "accuracy", "founded", "launched", "released", "cost", "price", "funding", "gdp", "population", "speed", "bandwidth", "performance"}
    subject = entities or sorted(claim_terms(claim.text) - metric_terms)
    if any(term in text for term in ("revenue", "profit", "sales", "valuation", "funding", "market cap", "arr", "mrr")):
        measure = "official financial results"
    elif any(term in text for term in ("latency", "throughput", "uptime", "accuracy", "capacity", "bandwidth", "api", "gpu", "cpu", "benchmark", "response time")):
        measure = "technical specification benchmark"
    elif any(term in text for term in ("height", "tall", "length", "distance", "wide", "deep")):
        measure = "current height measurement official"
    elif any(term in text for term in ("founded", "launched", "released", "introduced", "opened", "started")):
        measure = "official date history"
    elif any(term in text for term in ("grew", "growth", "increased", "decreased", "share", "percent", "%")):
        measure = "statistic official data"
    else:
        measure = "official data"
    years = re.findall(r"\b(?:19|20)\d{2}\b", claim.text)
    figures = [re.sub(r"[$€£₹]", "", match.group(0)).strip() for match in NUMBER_RE.finditer(claim.text)]
    figures = list(dict.fromkeys(value for value in figures if value))[:3]
    return " ".join(subject[:7] + [measure] + figures + list(dict.fromkeys(years)))[:240]


def verify_claim(claim: Claim, limit: int = 5) -> dict[str, Any]:
    # Search with the stated value, without it, and with a focused entity/metric
    # query. This reduces confirmation bias and finds first-party references.
    per_query = max(1, limit // 3)
    hits = web_search(claim.text, per_query)
    broad_query = NUMBER_RE.sub(lambda match: match.group(0) if re.fullmatch(r"(?:19|20)\d{2}", match.group(0).strip()) else " ", claim.text)
    broad_query = re.sub(r"\s+", " ", broad_query).strip(" ,.;:-")
    queries = []
    if broad_query and broad_query.casefold() != claim.text.casefold():
        queries.append(broad_query)
    focused_query = focused_claim_query(claim)
    if focused_query.casefold() not in {claim.text.casefold(), broad_query.casefold()}:
        queries.append(focused_query)
    for query in queries:
        if len(hits) >= limit:
            break
        known = {existing.get("url") or existing.get("title") for existing in hits}
        for hit in web_search(query, max(1, min(per_query, limit - len(hits)))):
            key = hit.get("url") or hit.get("title")
            if key and key not in known:
                hits.append(hit)
                known.add(key)
                if len(hits) >= limit:
                    break
    hits = hits[:limit]
    if not hits:
        return {"status": "Needs review", "confidence": "Low", "explanation": "The search providers returned no usable sources, so this claim could not be verified. No results do not prove the claim false; try again or add a search provider key.", "real_fact": "No sources were returned, so no correction could be established.", "sources": []}

    # Read the source pages themselves. Search snippets are retained as a
    # fallback, but a snippet alone cannot produce a Verified verdict.
    with ThreadPoolExecutor(max_workers=min(4, len(hits))) as pool:
        futures = {pool.submit(fetch_source_text, hit.get("url", "")): hit for hit in hits if hit.get("url")}
        for future in as_completed(futures):
            hit = futures[future]
            hit["page_text"] = future.result()

    claim_tokens = claim_terms(claim.text)
    claim_entity_tokens = claim_entities(claim.text)
    claim_matches = list(NUMBER_RE.finditer(claim.text))
    claim_facts = []
    for match in claim_matches:
        raw = match.group(0)
        value, family = number_signature(raw)
        if value == 0:
            continue
        if family == "count:" and value.is_integer() and 1900 <= value <= 2099:
            continue  # Usually a publication/year reference, not the statistic.
        claim_facts.append((value, family, raw))
    claim_dates = date_signatures(claim.text)
    requires_date_match = bool(claim_dates) and (claim.kind == "Date" or not claim_facts or claim.kind in {"Financial", "Technical", "Statistic"})
    if claim.kind == "Date":
        claim_facts = []

    relevant_hits = []
    for hit in hits:
        full_text = hit.get("page_text", "")
        segments = split_evidence(full_text) if full_text else []
        if not segments:
            segments = split_evidence(hit.get("snippet", ""))
        ranked = []
        for segment in segments:
            overlap = claim_tokens & claim_terms(segment)
            if len(overlap) >= min(2, max(1, len(claim_tokens))):
                ranked.append((len(overlap) / max(1, len(claim_tokens)), segment, overlap))
        ranked.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        if ranked:
            evidence = [item[1] for item in ranked[:4]]
            evidence_text = " ".join(evidence)
            records = []
            for segment in evidence:
                signatures = [number_signature(match.group(0)) for match in NUMBER_RE.finditer(segment) if entity_near_number(segment, match.start(), match.end(), claim_entity_tokens)]
                signatures = [item for item in signatures if item[0] != 0]
                matched = [fact for fact in claim_facts if any(numeric_values_match(value, fact[0]) and same_numeric_family(family, fact[1]) for value, family in signatures)]
                conflicts = [item for item in signatures if any(same_numeric_family(item[1], fact[1]) for fact in claim_facts) and not any(numeric_values_match(item[0], fact[0]) and same_numeric_family(item[1], fact[1]) for fact in claim_facts)]
                evidence_dates = date_signatures(segment)
                matching_dates = {wanted for wanted in claim_dates if any(candidate.startswith(wanted) or wanted.startswith(candidate) for candidate in evidence_dates)}
                conflicting_dates = {candidate for candidate in evidence_dates if not any(wanted.startswith(candidate) or candidate.startswith(wanted) for wanted in claim_dates) and any(len(candidate) == len(wanted) or (len(wanted) == 4 and len(candidate) > 4) for wanted in claim_dates)}
                record = {"text": segment, "matched_facts": matched, "conflicting_facts": conflicts, "matched_dates": matching_dates, "conflicting_dates": conflicting_dates}
                record["supports"] = bool((not claim_facts or len(matched) == len(claim_facts)) and (not requires_date_match or matching_dates) and (claim_facts or (requires_date_match and matching_dates)))
                record["conflicts"] = bool(conflicts or (requires_date_match and conflicting_dates and (matched or not claim_facts)))
                records.append(record)
            relevant_hits.append({**hit, "evidence": evidence, "page_opened": bool(full_text), "records": records, "matched_facts": [fact for record in records for fact in record["matched_facts"]], "conflicting_facts": [fact for record in records for fact in record["conflicting_facts"]], "matched_dates": {date for record in records for date in record["matched_dates"]}, "conflicting_dates": {date for record in records for date in record["conflicting_dates"]}, "evidence_text": evidence_text})

    support_sources = [hit for hit in relevant_hits if (hit["page_opened"] or source_quality(hit.get("url", ""), claim)[1] == "verified") and any(record["supports"] for record in hit["records"])]
    conflict_sources = [hit for hit in relevant_hits if (hit["page_opened"] or source_quality(hit.get("url", ""), claim)[1] == "verified") and any(record["conflicts"] for record in hit["records"])]
    support_domains = {urlparse(hit.get("url", "")).netloc.casefold() for hit in support_sources}
    conflict_domains = {urlparse(hit.get("url", "")).netloc.casefold() for hit in conflict_sources}
    trusted_support = [hit for hit in support_sources if source_quality(hit.get("url", ""), claim)[1] == "verified"]
    trusted_conflict = [hit for hit in conflict_sources if source_quality(hit.get("url", ""), claim)[1] == "verified"]
    if support_sources and conflict_sources and trusted_support and not trusted_conflict:
        status = "Verified"
        confidence = "Moderate"
        explanation = "An official, established or entity-matching source supports the stated figure. Other retrieved pages differ; the primary-looking source is linked below, so check its date and scope."
        real_fact = ""
    elif support_sources and conflict_sources and trusted_conflict and not trusted_support:
        status = "Inaccurate"
        confidence = "Moderate"
        explanation = "An official, established or entity-matching source contradicts the stated figure. The source excerpt below is the strongest correction lead; check its date and scope."
        real_fact = trusted_conflict[0]["evidence"][0]
    elif support_sources and conflict_sources:
        if len(support_domains) >= 2 and len(support_domains) > len(conflict_domains):
            status, confidence = "Verified", "Moderate"
            explanation = f"Relevant source text supports the figure on {len(support_domains)} distinct domains, more than the {len(conflict_domains)} domain(s) showing a different value. Check those differences for stale data or a different scope."
            real_fact = conflict_sources[0]["evidence"][0]
        elif len(conflict_domains) >= 2 and len(conflict_domains) > len(support_domains):
            status, confidence = "Inaccurate", "Moderate"
            explanation = f"Relevant source text shows a different figure on {len(conflict_domains)} distinct domains, more than the {len(support_domains)} domain(s) supporting the claim. The excerpt is a correction lead; confirm scope and dates."
            real_fact = conflict_sources[0]["evidence"][0]
        else:
            status, confidence = "Needs review", "Low"
            explanation = "Retrieved source passages disagree: some support the stated figure while others show a different value. Compare source date, scope and definitions."
            real_fact = conflict_sources[0]["evidence"][0]
    elif support_sources:
        status = "Verified"
        confidence = "High" if len(support_domains) >= 2 else "Moderate"
        detail = "date and figure" if claim_facts and requires_date_match else "date" if requires_date_match else "figure" if len(claim_facts) == 1 else "figures"
        opened_supports = sum(1 for source in support_sources if source.get("page_opened"))
        excerpt_supports = len(support_sources) - opened_supports
        basis = f"opened source text on {opened_supports} domain(s)" if not excerpt_supports else f"opened source text on {opened_supports} domain(s) and recognized live search excerpts on {excerpt_supports} domain(s)"
        explanation = f"The claim's {detail} is directly supported by {basis}. Check the source date and scope before relying on it."
        real_fact = ""
    elif conflict_sources:
        real_fact = conflict_sources[0]["evidence"][0]
        independently_supported = len(conflict_domains) >= 2 or bool(trusted_conflict)
        if independently_supported:
            status = "Inaccurate"
            confidence = "High" if len(conflict_domains) >= 3 else "Moderate"
            explanation = f"Relevant source-page text shows a different value for the same unit in {len(conflict_domains)} distinct domain(s). The excerpt below is a candidate correction; confirm date, scope and definition."
        else:
            status, confidence = "Needs review", "Low"
            explanation = "One relevant source page shows a different value, but independent confirmation was not found. Treat its excerpt as a correction lead and review the date, scope and definition."
    elif not relevant_hits:
        status, confidence = "False", "Low"
        explanation = "No relevant evidence was found in the source pages returned by live search. This marks the claim unsupported; lack of evidence alone does not prove it false."
        real_fact = "No correction could be established from the retrieved source pages."
    elif not any(hit["page_opened"] for hit in relevant_hits):
        status, confidence = "Needs review", "Low"
        explanation = "Search snippets looked relevant, but the original source pages could not be opened. Snippets alone are not enough to verify or correct a figure."
        real_fact = "Open the listed source pages to confirm the current value and context."
    else:
        status, confidence = "Needs review", "Low"
        explanation = "Relevant source text was found, but it did not directly support or clearly contradict the figure. Human review is needed."
        real_fact = relevant_hits[0]["evidence"][0]

    corroborating_hits = [hit for hit in relevant_hits if any(record["supports"] or record["conflicts"] for record in hit["records"])]
    selected = corroborating_hits or relevant_hits or hits[:min(3, len(hits))]
    for hit in selected:
        hit.setdefault("evidence", [hit.get("snippet", "")])
    return {"status": status, "confidence": confidence, "explanation": explanation, "real_fact": real_fact, "sources": selected}


def run_all(claims: list[Claim], limit: int = 5) -> list[dict[str, Any]]:
    results = []
    bar = st.progress(0, text="Searching live sources…")
    for i, claim in enumerate(claims):
        results.append(verify_claim(claim, limit))
        bar.progress((i + 1) / len(claims), text=f"Checking claim {i + 1} of {len(claims)}")
        time.sleep(.15)
    bar.empty()
    return results


def create_pdf_report(filename: str, page_count: int, word_count: int, claims: list[Claim], results: list[dict[str, Any]], reviews: list[dict[str, str]], run_time: str) -> bytes:
    """Create a multi-page, source-linked PDF with the full review trail."""
    fonts_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    if "FactCheck" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("FactCheck", os.path.join(fonts_dir, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("FactCheck-Bold", os.path.join(fonts_dir, "VeraBd.ttf")))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=22*mm, bottomMargin=19*mm, title=f"FactCheck Report — {filename}", author="FactCheck Truth Layer")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="FC_Title", parent=styles["Title"], fontName="FactCheck-Bold", fontSize=23, leading=29, textColor=colors.HexColor("#14233b"), alignment=0, spaceAfter=5))
    styles.add(ParagraphStyle(name="FC_Sub", parent=styles["Normal"], fontName="FactCheck", fontSize=9, leading=14, textColor=colors.HexColor("#65758c"), spaceAfter=4))
    styles.add(ParagraphStyle(name="FC_H2", parent=styles["Heading2"], fontName="FactCheck-Bold", fontSize=13, leading=17, textColor=colors.HexColor("#14233b"), spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="FC_Body", parent=styles["BodyText"], fontName="FactCheck", fontSize=9, leading=13, textColor=colors.HexColor("#35445a"), spaceAfter=4, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="FC_Small", parent=styles["BodyText"], fontName="FactCheck", fontSize=7.5, leading=10, textColor=colors.HexColor("#68778c"), wordWrap="CJK"))
    styles.add(ParagraphStyle(name="FC_Tag", parent=styles["BodyText"], fontName="FactCheck-Bold", fontSize=8, leading=11, textColor=colors.HexColor("#087e72"), spaceAfter=3))
    def p(value: Any, style: str = "FC_Body") -> Paragraph:
        return Paragraph(xml_escape(str(value)).replace("\n", "<br/>"), styles[style])
    story: list[Any] = [p("FACTCHECK / EVIDENCE REPORT", "FC_Tag"), p("Document verification", "FC_Title"), p(filename, "FC_Sub"), p(f"Checked {run_time}  ·  {page_count} pages  ·  {word_count:,} words  ·  {len(results)} claims checked", "FC_Sub"), Spacer(1, 5*mm)]
    totals = {status: sum(1 for result in results if result["status"] == status) for status in ["Verified", "Inaccurate", "False", "Needs review"]}
    summary_rows = [[p("VERIFIED", "FC_Tag"), p("INACCURATE", "FC_Tag"), p("FALSE / UNSUPPORTED", "FC_Tag"), p("NEEDS REVIEW", "FC_Tag")], [p(str(totals["Verified"]), "FC_H2"), p(str(totals["Inaccurate"]), "FC_H2"), p(str(totals["False"]), "FC_H2"), p(str(totals["Needs review"]), "FC_H2")]]
    summary = Table(summary_rows, colWidths=[42*mm]*4)
    summary.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f2f6fa")), ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#e1e8f0")), ("INNERGRID", (0,0), (-1,-1), .4, colors.HexColor("#e1e8f0")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 9), ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story += [summary, Spacer(1, 4*mm), p("How to read this report", "FC_H2"), p("Automated verdicts are research triage. An exact figure match is not proof that the claim is correct in context; an unsupported result does not prove the opposite. Confirm definitions, time period, geography and the original source before publishing."), p("Claim-by-claim findings", "FC_H2"), HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dce5ed"), spaceAfter=7)]
    for index, (claim, result) in enumerate(zip(claims, results), 1):
        review = reviews[index - 1] if index - 1 < len(reviews) else {}
        verdict = review.get("status") or result["status"]
        story += [p(f"{index:02d}  /  {verdict.upper()}   ·   {claim.kind.upper()}   ·   PAGE {claim.page}   ·   CONFIDENCE {result.get('confidence', 'Low').upper()}", "FC_Tag"), p(claim.text, "FC_Body"), p("Automated assessment: " + result["explanation"], "FC_Small")]
        if review:
            story.append(p("Reviewer decision: " + review.get("status", "") + ("  ·  " + review["note"] if review.get("note") else ""), "FC_Body"))
        if result.get("real_fact"):
            story += [p("Candidate correction / search lead", "FC_Tag"), p(result["real_fact"], "FC_Body")]
        if result.get("sources"):
            story.append(p("SOURCE EVIDENCE", "FC_Tag"))
            for source in result["sources"]:
                quality, _ = source_quality(source.get("url", ""), claim)
                story.append(p(f"{source.get('title', 'Source')}  ·  {quality}", "FC_Body"))
                story.append(p(source_access_label(source, claim), "FC_Small"))
                if source.get("url", "").startswith(("http://", "https://")):
                    safe_url = xml_escape(source["url"], {"\"": "&quot;"})
                    story.append(Paragraph(f'<link href="{safe_url}" color="#087e72">Open original source</link>', styles["FC_Small"]))
                source_excerpt = " ".join(source.get("evidence", [])) or source.get("snippet", "")
                if source_excerpt:
                    story.append(p(source_excerpt, "FC_Small"))
                story.append(Spacer(1, 2*mm))
        else:
            story.append(p("No source links were returned for this claim.", "FC_Small"))
        story += [HRFlowable(width="100%", thickness=.5, color=colors.HexColor("#e3e9ef"), spaceBefore=4, spaceAfter=8)]
    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e2e8ef"))
        canvas.line(18*mm, 14*mm, A4[0]-18*mm, 14*mm)
        canvas.setFont("FactCheck", 7)
        canvas.setFillColor(colors.HexColor("#7a8798"))
        canvas.drawString(18*mm, 9*mm, "FactCheck · Evidence-first review")
        canvas.drawRightString(A4[0]-18*mm, 9*mm, f"Page {document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


st.markdown('<div class="workspace-head"><div><div class="eyebrow" style="color:#087e72">RESEARCH WORKSPACE / 01</div><div style="font:800 20px Manrope;color:#18263c">FactCheck <span style="color:#8b97a8;font-weight:500">· Truth Layer</span></div></div><div class="tag unclear">LIVE WEB EVIDENCE</div></div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">CLAIM INTELLIGENCE · DOCUMENT REVIEW</div><h1>Every claim has a trail.<br>Make yours easy to trust.</h1><p>Surface statistics, dates and financial figures from marketing documents. Check them against live sources, review the evidence and export a decision-ready report.</p><div class="hero-meta"><span class="hero-pill">01 / EXTRACT</span><span class="hero-pill">02 / CROSS-CHECK</span><span class="hero-pill">03 / REVIEW</span><span class="hero-pill">04 / REPORT</span></div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='font:800 19px Manrope'>◉ FactCheck</div>", unsafe_allow_html=True)
    st.caption("Evidence workspace for teams that publish facts.")
    st.markdown("---")
    st.markdown("**WORKFLOW**")
    st.markdown("**01** Upload a PDF\n\n**02** Select claims\n\n**03** Search the web\n\n**04** Review and export")
    st.markdown("---")
    st.markdown("**VERDICT KEY**")
    st.caption("Verified · Figure appears in relevant evidence")
    st.caption("Inaccurate · Sources surface a different figure")
    st.caption("False · No relevant support found")
    st.caption("Needs review · Evidence is inconclusive")
    st.markdown("---")
    st.caption("A search result is a lead, not a substitute for checking scope, date and source context.")

uploaded = st.file_uploader("Upload a document", type=["pdf"], help=f"PDF · Up to {MAX_PDF_MB} MB · Text-readable documents work best")
if uploaded:
    if uploaded.size > MAX_PDF_MB * 1024 * 1024:
        st.error(f"Please upload a PDF smaller than {MAX_PDF_MB} MB.")
        st.stop()
    pdf_bytes = uploaded.getvalue()
    doc_id = hashlib.sha256(pdf_bytes).hexdigest()[:20]
    if st.session_state.get("document_id") != doc_id:
        for key in list(st.session_state.keys()):
            if key in {"results", "checked_claims", "claims", "document_id", "single_result", "single_claim"} or key.startswith(("decision-", "note-", "save-", "review-")):
                del st.session_state[key]
        st.session_state.document_id = doc_id
    try:
        text, pages = pdf_text(pdf_bytes)
    except Exception as exc:
        st.error(f"Could not read this PDF: {html.escape(str(exc))}")
        st.stop()
    if not text.strip():
        st.warning("This PDF has no selectable text. OCR is not enabled yet; export a text-readable PDF and try again.")
        st.stop()
    claims = extract_claims(pages)
    kind_counts = {kind: sum(1 for claim in claims if claim.kind == kind) for kind in ["Statistic", "Date", "Financial", "Technical"]}
    st.markdown('<div class="panel upload-panel">', unsafe_allow_html=True)
    file_col, info_col = st.columns([3, 2], vertical_alignment="center")
    with file_col:
        st.markdown(f"### ◈ {html.escape(uploaded.name)}")
        breakdown = "  ·  ".join(f"{count} {kind.lower()}" for kind, count in kind_counts.items() if count)
        st.caption(f"{len(pages)} pages  ·  {len(text.split()):,} words  ·  {len(claims)} candidate claims" + (f"  ·  {breakdown}" if breakdown else "") + "  ·  PDF parsed successfully")
    with info_col:
        st.markdown(f"<div style='text-align:right;color:#728197;font:11px DM Mono'>DOCUMENT ID&nbsp; {doc_id[:10].upper()}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if claims:
        with st.expander("Review extracted claims", expanded=False):
            st.caption("Check that page references and sentence boundaries look right before searching. Extraction focuses on checkable figures and dates; it may miss claims in scanned pages or complex tables.")
            st.dataframe(
                [{"Page": claim.page, "Claim type": claim.kind, "Detected claim": claim.text} for claim in claims],
                hide_index=True,
                width="stretch",
                height=min(420, 46 + 42 * min(len(claims), 9)),
            )

    if not claims:
        st.info("No checkable numeric or date claims were detected. Scanned PDFs and broad qualitative claims need manual review.")
    else:
        st.markdown("### Build your check run")
        control_a, control_b = st.columns([1.3, 1], vertical_alignment="bottom")
        with control_a:
            run_scope = st.radio("Claim selection", ["Check all detected claims", "Choose claims"], horizontal=True, key=f"scope-{doc_id}")
        with control_b:
            search_depth = st.selectbox("Evidence depth", ["Expanded · 6 sources (recommended)", "Focused · 3 sources"], key=f"depth-{doc_id}", help="Expanded searches test more queries and source leads; focused is faster.")
        claim_labels = [f"p.{c.page} · {c.kind} · {c.text}" for c in claims]
        if run_scope == "Choose claims":
            selected_labels = st.multiselect("Select claims for this run", claim_labels, placeholder="Choose one or more extracted claims")
            selected_claims = [c for label, c in zip(claim_labels, claims) if label in selected_labels]
        else:
            selected_claims = claims
            st.caption(f"{len(claims)} extracted claims are ready to check.")
        limit = 3 if search_depth.startswith("Focused") else 6
        run_col, hint_col = st.columns([1, 2], vertical_alignment="center")
        with run_col:
            if st.button("⌕  Run evidence check", type="primary", disabled=not selected_claims, width="stretch"):
                st.session_state.results = run_all(selected_claims, limit)
                st.session_state.checked_claims = selected_claims
                st.session_state.run_time = datetime.now().strftime("%d %b %Y · %H:%M")
                st.session_state.run_depth = "expanded" if limit == 6 else "focused"
        with hint_col:
            st.caption("Each result includes matching context, source links, a confidence cue and a page reference.")

    with st.expander("＋ Check a single claim", expanded=False):
        st.caption("Search one statement directly, without adding it to the document findings.")
        with st.form(f"single-claim-form-{doc_id}"):
            manual_claim = st.text_area("Claim to verify", placeholder="Example: The company generated $4.2 billion in revenue in 2024.", height=90, label_visibility="collapsed")
            manual_depth = st.selectbox("Search depth", ["Expanded · 6 sources (recommended)", "Focused · 3 sources"], key=f"manual-depth-{doc_id}")
            submit_manual = st.form_submit_button("Check this claim", type="primary")
        if submit_manual and manual_claim.strip():
            st.session_state.single_claim = manual_claim.strip()
            st.session_state.single_result = verify_claim(Claim(manual_claim.strip(), 0, "Manual claim"), 3 if manual_depth.startswith("Focused") else 6)
        if st.session_state.get("single_result"):
            manual_result = st.session_state.single_result
            mcls = {"Verified": "verified", "Inaccurate": "inaccurate", "False": "false"}.get(manual_result["status"], "unclear")
            st.markdown(f'<div class="claim"><span class="tag {mcls}">{manual_result["status"].upper()}</span><span class="tag unclear">CONFIDENCE · {manual_result.get("confidence", "Low").upper()}</span><div class="claimline">{html.escape(st.session_state.single_claim)}</div><div class="small">{html.escape(manual_result["explanation"])}</div></div>', unsafe_allow_html=True)
            for source in manual_result["sources"]:
                manual_claim_obj = Claim(st.session_state.single_claim, 0, "Manual claim")
                qlabel, qclass = source_quality(source.get("url", ""), manual_claim_obj)
                page_state = source_access_label(source, manual_claim_obj)
                source_excerpt = " ".join(source.get("evidence", [])) or source.get("snippet", "")
                st.markdown(f'<div class="evidence"><span class="tag {qclass}">{html.escape(qlabel)}</span><span class="tag unclear">{page_state}</span><a href="{html.escape(source.get("url", ""), quote=True)}" target="_blank">{html.escape(source.get("title", "Source"))} ↗</a><br>{html.escape(source_excerpt[:700])}</div>', unsafe_allow_html=True)

    if st.session_state.get("results") and st.session_state.get("document_id") == doc_id:
        results = st.session_state.results
        checked_claims = st.session_state.checked_claims
        counts = {s: sum(1 for r in results if r["status"] == s) for s in ["Verified", "Inaccurate", "False", "Needs review"]}
        st.markdown("---")
        summary_left, summary_right = st.columns([3, 1], vertical_alignment="center")
        with summary_left:
            st.markdown("### Evidence overview")
            opened_pages = sum(1 for result in results for source in result["sources"] if source.get("page_opened"))
            total_sources = sum(len(result["sources"]) for result in results)
            st.caption(f"Run {st.session_state.get('run_time', '')}  ·  {len(results)} claims checked  ·  {opened_pages}/{total_sources} source pages opened  ·  Search depth: {st.session_state.get('run_depth', 'focused')}")
        with summary_right:
            st.markdown(f"<div style='text-align:right;font:11px DM Mono;color:#7d8aa0'>COVERAGE<br><b style='font:700 24px Manrope;color:#152642'>{len(results)}/{len(claims)}</b></div>", unsafe_allow_html=True)
        cols = st.columns(4)
        for col, label in zip(cols, counts):
            col.metric(label, counts[label])

        reviews = [st.session_state.get(f"review-{idx}", {}) for idx in range(1, len(results) + 1)]
        pdf_report = create_pdf_report(uploaded.name, len(pages), len(text.split()), checked_claims, results, reviews, st.session_state.get("run_time", ""))
        report_name = re.sub(r"[^A-Za-z0-9_-]+", "-", uploaded.name.rsplit(".", 1)[0]).strip("-") or "document"
        st.download_button("⇩  Download detailed PDF report", pdf_report, file_name=f"{report_name}-factcheck-report.pdf", mime="application/pdf")
        st.caption("Verification method: the checker opens live source pages, compares matching evidence text and figures, and looks for conflicting values. A snippet can support a verdict only from an official, established or entity-matching domain; otherwise it remains a review lead. Source publication dates and scope still need human review.")

        with st.container(border=True):
            st.markdown(f'<div class="filter-heading"><span class="filter-title">Filter findings</span><span class="filter-count">{len(results)} total claims</span></div>', unsafe_allow_html=True)
            filter_a, filter_b, filter_c = st.columns([1, 1, 1.65], vertical_alignment="bottom")
            with filter_a:
                status_option = st.selectbox("Verdict", ["All verdicts"] + list(counts), key=f"status-filter-{doc_id}", label_visibility="visible")
            with filter_b:
                kind_options = sorted({c.kind for c in checked_claims})
                kind_option = st.selectbox("Claim type", ["All types"] + kind_options, key=f"kind-filter-{doc_id}", label_visibility="visible")
            with filter_c:
                claim_search = st.text_input("Search claims", placeholder="Type a word or phrase", key=f"claim-search-{doc_id}")
        status_filter = list(counts) if status_option == "All verdicts" else [status_option]
        kind_filter = kind_options if kind_option == "All types" else [kind_option]

        st.markdown("### Claim review")
        visible = 0
        for idx, (claim, result) in enumerate(zip(checked_claims, results), 1):
            if result["status"] not in status_filter or claim.kind not in kind_filter or (claim_search and claim_search.casefold() not in claim.text.casefold()):
                continue
            visible += 1
            review = st.session_state.get(f"review-{idx}", {})
            status = result["status"]
            status_cls = {"Verified": "verified", "Inaccurate": "inaccurate", "False": "false"}.get(status, "unclear")
            review_tag = f'<span class="tag reviewed">REVIEWED · {html.escape(review["status"].upper())}</span>' if review else ""
            confidence = result.get("confidence", "Low")
            st.markdown(f'<div class="claim"><span class="tag {status_cls}">{status.upper()}</span><span class="tag unclear">{claim.kind.upper()}</span><span class="tag unclear">CONFIDENCE · {confidence.upper()}</span><span class="tag unclear">PAGE {claim.page}</span>{review_tag}<div class="claimline">{html.escape(claim.text)}</div><div class="small">{html.escape(result["explanation"])}</div></div>', unsafe_allow_html=True)
            # Show correction leads only for unresolved or contradicted claims.
            # For verified claims, source evidence below is clearer than a
            # generic conflicting excerpt that may refer to a different scope.
            if result["real_fact"] and status in {"Inaccurate", "False", "Needs review"}:
                lead_label = "Candidate correction" if status == "Inaccurate" else "Evidence requiring review"
                st.markdown(f'<div class="evidence"><div class="evidence-head"><span class="tag {status_cls}">{lead_label.upper()}</span></div><p class="source-excerpt">{html.escape(result["real_fact"][:520])}</p></div>', unsafe_allow_html=True)
            if result["sources"]:
                st.markdown('<div class="section-label">Retrieved source evidence</div>', unsafe_allow_html=True)
                source_columns = st.columns(2)
                for source_i, source in enumerate(result["sources"]):
                    quality, qclass = source_quality(source.get("url", ""), claim)
                    url = html.escape(source.get("url", ""), quote=True)
                    title = html.escape(source.get("title", "Source"))
                    evidence_items = source.get("evidence", [])
                    source_excerpt = (evidence_items[0] if evidence_items else source.get("snippet", ""))
                    snippet = html.escape(source_excerpt[:360])
                    page_state = source_access_label(source, claim)
                    if url:
                        with source_columns[source_i % 2]:
                            host = html.escape(urlparse(source.get("url", "")).netloc.removeprefix("www."))
                            st.markdown(f'<div class="evidence"><div class="evidence-head"><span class="source-domain">{host}</span><span class="tag {qclass}">{html.escape(quality)}</span></div><a class="source-title" href="{url}" target="_blank" rel="noopener">{title} ↗</a><div class="evidence-head"><span class="tag unclear">{page_state}</span></div><p class="source-excerpt">{snippet}</p></div>', unsafe_allow_html=True)
            with st.expander("Record reviewer decision", expanded=False):
                st.radio("Reviewer verdict", ["Verified", "Inaccurate", "False", "Needs review"], key=f"decision-{idx}", horizontal=True, label_visibility="collapsed")
                st.text_input("Reviewer note / corrected fact", key=f"note-{idx}", placeholder="Record corrected figure, scope or source")
                if st.button("Save review decision", key=f"save-{idx}"):
                    st.session_state[f"review-{idx}"] = {"status": st.session_state[f"decision-{idx}"], "note": st.session_state[f"note-{idx}"]}
                    st.rerun()
        if not visible:
            st.info("No claims match these filters.")
        st.caption("Domain labels are quick source cues, not endorsements. Machine verdicts are triage signals; confirm source context, geography, date and definition before publishing.")
else:
    st.markdown('<div class="panel upload-panel"><div class="eyebrow" style="color:#087e72">YOUR REVIEW DESK</div><h3 style="margin:10px 0 6px">Start with a document</h3><div class="small">Upload a text-readable PDF to extract candidate claims, preserve page references and build a source-linked review.</div></div>', unsafe_allow_html=True)
