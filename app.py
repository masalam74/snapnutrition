import streamlit as st
from PIL import Image
import base64
from groq import Groq
import json
import io
import re
import requests

st.set_page_config(page_title="SnapNutrition Pro", layout="centered")

st.title("📸 SnapNutrition Pro")
st.caption("Take a photo or upload - AI analyzes each food item individually")

# Your Groq API key (from secrets)
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)

# Google Sheets webhook (from secrets)
GOOGLE_SHEETS_WEBHOOK = st.secrets["GOOGLE_SHEETS_WEBHOOK"]

# Email validation function
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Save email to Google Sheets
def save_email_to_sheets(email, scan_count):
    """Send email to Google Sheets webhook"""
    try:
        response = requests.post(
            GOOGLE_SHEETS_WEBHOOK,
            json={"email": email, "scan_count": scan_count, "status": "active"},
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

# Nutrition database
def get_nutrition_by_food_name(food_name):
    nutrition_db = {
        "apple": {"calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3},
        "banana": {"calories": 105, "protein_g": 1.3, "carbs_g": 27, "fat_g": 0.4},
        "chicken": {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6},
        "shrimp": {"calories": 84, "protein_g": 18, "carbs_g": 0, "fat_g": 0.9},
        "rice": {"calories": 206, "protein_g": 4, "carbs_g": 45, "fat_g": 0.5},
        "biryani": {"calories": 350, "protein_g": 12, "carbs_g": 45, "fat_g": 12},
        "kebab": {"calories": 250, "protein_g": 20, "carbs_g": 5, "fat_g": 16},
        "fries": {"calories": 365, "protein_g": 4, "carbs_g": 48, "fat_g": 17},
        "salad": {"calories": 150, "protein_g": 5, "carbs_g": 15, "fat_g": 8},
        "bread": {"calories": 265, "protein_g": 9, "carbs_g": 49, "fat_g": 3.2},
        "naan": {"calories": 120, "protein_g": 4, "carbs_g": 20, "fat_g": 3},
        "beef curry": {"calories": 400, "protein_g": 30, "carbs_g": 10, "fat_g": 25},
        "avocado": {"calories": 160, "protein_g": 2, "carbs_g": 8.5, "fat_g": 14.7},
    }
    
    food_lower = food_name.lower().strip()
    
    if food_lower in nutrition_db:
        return nutrition_db[food_lower]
    
    for key, value in nutrition_db.items():
        if key in food_lower:
            return value
    
    return None

def resize_image_for_api(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    width, height = image.size
    current_pixels = width * height
    max_pixels = 33177600
    
    if current_pixels > max_pixels:
        ratio = (max_pixels / current_pixels) ** 0.5
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGB')
    
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=85)
    return img_byte_arr.getvalue()

def encode_image_to_base64(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

# Initialize session state
if 'items_data' not in st.session_state:
    st.session_state.items_data = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'scan_count' not in st.session_state:
    st.session_state.scan_count = 0
if 'current_image_bytes' not in st.session_state:
    st.session_state.current_image_bytes = None
if 'current_file_name' not in st.session_state:
    st.session_state.current_file_name = None
if 'email' not in st.session_state:
    st.session_state.email = None
if 'email_captured' not in st.session_state:
    st.session_state.email_captured = False
if 'extra_scans_added' not in st.session_state:
    st.session_state.extra_scans_added = False

# ========== CAMERA + UPLOAD OPTIONS ==========
st.subheader("📷 How would you like to capture your food?")

input_method = st.radio(
    "Choose option:", 
    ["📸 Take a photo with camera", "📁 Upload from gallery"],
    horizontal=True,
    label_visibility="collapsed"
)

# Track if image has changed
image_bytes = None
current_file_id = None

if input_method == "📸 Take a photo with camera":
    camera_image = st.camera_input("Point camera at your food", label_visibility="collapsed")
    if camera_image:
        image_bytes = camera_image.getvalue()
        st.image(camera_image, caption="Your meal", width=350)
        current_file_id = "camera_capture"
else:
    uploaded_file = st.file_uploader("Upload a food photo", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if uploaded_file:
        image_bytes = uploaded_file.getvalue()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption="Your meal", width=350)
        current_file_id = uploaded_file.name

# Clear results when new file is selected
if current_file_id is not None and current_file_id != st.session_state.current_file_name:
    st.session_state.items_data = None
    st.session_state.edit_mode = False
    st.session_state.current_file_name = current_file_id
    st.session_state.current_image_bytes = image_bytes

# ========== EMAIL CAPTURE (After 3 scans) ==========
if st.session_state.scan_count >= 3 and not st.session_state.email_captured and not st.session_state.extra_scans_added:
    st.warning("🎁 You've used 3 scans! Get 2 FREE extra scans by sharing your email.")
    
    with st.form(key="email_form"):
        email_input = st.text_input("Email address:", placeholder="you@example.com")
        submit_email = st.form_submit_button("Get 2 More Free Scans")
        
        if submit_email:
            if is_valid_email(email_input):
                # Save to Google Sheets via webhook
                success = save_email_to_sheets(email_input, st.session_state.scan_count)
                if success:
                    st.session_state.email = email_input
                    st.session_state.email_captured = True
                    st.session_state.extra_scans_added = True
                    st.session_state.scan_count = max(0, st.session_state.scan_count - 2)
                    st.success("✅ Thanks! 2 extra scans added. Your email has been saved.")
                    st.rerun()
                else:
                    st.error("Could not save email. Please try again.")
            else:
                st.error("Please enter a valid email address.")

# ========== SCREENING FOR SCAN LIMIT ==========
scan_blocked = False
if st.session_state.scan_count >= 5 and not st.session_state.email_captured:
    scan_blocked = True
    st.warning("⚠️ Free limit reached (5 scans).")
    
    st.info("💡 **Ways to continue:**")
    st.markdown("""
    1. **Upgrade to Pro (€6.99/month)** → Unlimited scans + individual item breakdown
    2. **Share your email** (above) to get 2 extra free scans
    """)
    
    # Pro upgrade button (Lemon Squeezy link will go here)
    st.markdown("[🚀 Upgrade to Pro (€6.99/month)](https://buy.stripe.com/your-link-here)")
    
elif st.session_state.scan_count >= 7:
    scan_blocked = True
    st.error("🔴 Free limit reached (7 scans). Please upgrade to Pro to continue.")
    st.markdown("[🚀 Upgrade to Pro (€6.99/month)](https://buy.stripe.com/your-link-here)")

# ========== PROCESS IMAGE ==========
if image_bytes and not scan_blocked and st.button("🔍 Analyze Each Food Item", key="analyze_btn", type="primary", use_container_width=True):
    with st.spinner("🧠 AI identifying each food item..."):
        try:
            img_bytes = resize_image_for_api(image_bytes)
            base64_image = encode_image_to_base64(img_bytes)
            
            completion = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": """Analyze this food image and list EACH food item separately. Return ONLY valid JSON as an array. Example:
[
    {"food": "biryani", "calories": 350, "protein_g": 12, "carbs_g": 45, "fat_g": 12},
    {"food": "kebab", "calories": 250, "protein_g": 20, "carbs_g": 5, "fat_g": 16}
]

If only one food item, return array with one object. No other text."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = completion.choices[0].message.content
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            try:
                items = json.loads(result_text)
                if isinstance(items, dict):
                    items = [items]
                st.session_state.items_data = items
                st.session_state.scan_count += 1
                st.rerun()
            except json.JSONDecodeError:
                st.write("Raw response:", result_text)
                st.info("AI couldn't parse. Try clearer photo with distinct items.")
                
        except Exception as e:
            st.error(f"Error: {e}")

# ========== DISPLAY RESULTS ==========
if st.session_state.items_data:
    items = st.session_state.items_data
    
    if not st.session_state.edit_mode:
        st.balloons()
        st.success(f"✅ Found {len(items)} food items")
        
        total_calories = 0
        for idx, item in enumerate(items):
            with st.expander(f"🍽️ {item.get('food', 'Item')}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🔥 Calories", f"{item.get('calories', '?')} kcal")
                with col2:
                    st.metric("💪 Protein", f"{item.get('protein_g', '?')}g")
                with col3:
                    st.metric("🍚 Carbs", f"{item.get('carbs_g', '?')}g")
                with col4:
                    st.metric("🥑 Fat", f"{item.get('fat_g', '?')}g")
                total_calories += item.get('calories', 0)
        
        st.info(f"📊 **Total for this meal: {total_calories} calories**")
        st.caption("💡 Click Edit to correct any item or add/remove foods")
        
        if st.button("✏️ Edit Individual Items"):
            st.session_state.edit_mode = True
            st.rerun()
    
    else:
        # Edit mode - modify individual items
        st.info("✏️ **Edit Mode:** Modify each food item")
        
        updated_items = []
        for idx, item in enumerate(items):
            st.markdown(f"### Item {idx + 1}")
            
            corrected_food = st.text_input(
                f"Food name {idx + 1}:", 
                value=item.get('food', ''),
                key=f"food_{idx}"
            )
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                cal = st.number_input(f"Calories", value=int(item.get('calories', 0)), key=f"cal_{idx}")
            with col2:
                prot = st.number_input(f"Protein", value=int(item.get('protein_g', 0)), key=f"prot_{idx}")
            with col3:
                carbs = st.number_input(f"Carbs", value=int(item.get('carbs_g', 0)), key=f"carbs_{idx}")
            with col4:
                fat = st.number_input(f"Fat", value=int(item.get('fat_g', 0)), key=f"fat_{idx}")
            
            # Auto-lookup if name changed
            if corrected_food != item.get('food', ''):
                auto_nut = get_nutrition_by_food_name(corrected_food)
                if auto_nut:
                    st.success(f"✨ Auto-updated for {corrected_food}")
                    cal = auto_nut['calories']
                    prot = auto_nut['protein_g']
                    carbs = auto_nut['carbs_g']
                    fat = auto_nut['fat_g']
            
            updated_items.append({
                'food': corrected_food,
                'calories': cal,
                'protein_g': prot,
                'carbs_g': carbs,
                'fat_g': fat
            })
            st.markdown("---")
        
        # Add new item button
        if st.button("➕ Add Another Food Item"):
            updated_items.append({'food': 'New item', 'calories': 0, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 0})
            st.session_state.items_data = updated_items
            st.rerun()
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("✅ Save All Changes", type="primary"):
                st.session_state.items_data = updated_items
                st.session_state.edit_mode = False
                st.success("Saved!")
                st.rerun()
        with col_cancel:
            if st.button("❌ Cancel"):
                st.session_state.edit_mode = False
                st.rerun()

# Footer
st.markdown("---")
st.caption(f"💪 **Free scans used:** {st.session_state.scan_count}/5 today | ⭐ **Pro:** €6.99/month unlimited")

with st.sidebar:
    st.header("📱 How to use")
    st.write("**Option 1:** Tap 'Take a photo' and point camera at food")
    st.write("**Option 2:** Upload from gallery")
    st.markdown("---")
    st.write("🎁 **Get extra free scans:** Share your email after 3 scans")
    st.markdown("---")
    st.header("✨ Premium Features")
    st.write("- Individual item breakdown")
    st.write("- Edit any food name or nutrition fact")
    st.write("- Add/remove food items")
    st.write("- Unlimited scans")
    st.markdown("---")
    if st.session_state.email:
        st.success(f"📧 Email saved: {st.session_state.email}")
    st.caption("Made with ❤️ - Your AI Nutritionist")
# At the very bottom of your app.py
hide_streamlit_style = """
    <style>
    /* Hide all typical Streamlit branding */
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    header {display: none !important;}
    .stDeployButton {display: none !important;}
    .stAppDeployButton {display: none !important;}
    .css-1lsmgbg {display: none !important;}
    .viewerBadge_container__1QSob {display: none !important;}
    .st-emotion-cache-1lsmgbg {display: none !important;}

    /* Specifically target the footer element */
    .st-emotion-cache-1lsmgbg {display: none !important;}

    /* Mobile specific overrides */
    @media (max-width: 768px) {
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        .stAppDeployButton {display: none !important;}
        .st-emotion-cache-1lsmgbg {display: none !important;}
        .viewerBadge_container__1QSob {display: none !important;}
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
