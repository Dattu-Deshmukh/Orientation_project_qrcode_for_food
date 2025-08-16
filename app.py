import streamlit as st
from datetime import datetime
from PIL import Image
import io
import numpy as np

# Handle optional imports gracefully
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    st.error("❌ Google Sheets integration not available. Please install: pip install gspread oauth2client")
    GSPREAD_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    st.warning("⚠️ OpenCV not available. QR detection may be limited. Install with: pip install opencv-python-headless")
    CV2_AVAILABLE = False

# ========================
# QR CODE DETECTION FUNCTIONS  
# ========================

def detect_qr_with_opencv(image):
    """Try to detect QR code using OpenCV"""
    if not CV2_AVAILABLE:
        st.error("OpenCV not available for QR detection")
        return None
        
    try:
        # Convert PIL image to OpenCV format
        img_array = np.array(image)
        
        # Initialize QR code detector
        qr_detector = cv2.QRCodeDetector()
        
        # Detect and decode QR code
        data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(img_array)
        
        if data:
            return data
        return None
    except Exception as e:
        st.error(f"OpenCV detection error: {e}")
        return None

# ========================
# GOOGLE SHEETS CONNECTION
# ========================

@st.cache_resource
def init_google_sheets():
    """Initialize Google Sheets connection with caching"""
    if not GSPREAD_AVAILABLE:
        st.error("Google Sheets integration not available. Please install required packages.")
        return None
        
    try:
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        
        # Try to load credentials from Streamlit secrets first
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Fallback to local file
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
        client = gspread.authorize(creds)
        sheet = client.open("orientation_passes").sheet1
        return sheet
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.info("Please check your credentials configuration.")
        return None

def get_entry_statistics(sheet):
    """Get real-time entry statistics"""
    try:
        records = sheet.get_all_records()
        total_entries = sum(1 for row in records if row.get("EntryStatus") == "Entered")
        total_exits = sum(1 for row in records if row.get("ExitStatus") == "Exited")
        currently_present = total_entries - total_exits
        total_students = len(records)
        
        return {
            "total_entries": total_entries,
            "total_exits": total_exits,
            "currently_present": currently_present,
            "total_students": total_students
        }
    except Exception as e:
        return {
            "total_entries": "Error",
            "total_exits": "Error", 
            "currently_present": "Error",
            "total_students": "Error"
        }

def process_student_entry(qr_data, sheet):
    """Process the scanned student data for ENTRY ONLY"""
    try:
        records = sheet.get_all_records()
        found = False
        
        for i, row in enumerate(records, start=2):
            if str(row["ID"]) == str(qr_data):
                found = True
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Check current entry status
                entry_status = row.get("EntryStatus", "")
                
                # Only handle entry - no exit functionality
                if not entry_status or entry_status == "":
                    sheet.update_cell(i, 4, "Entered")  # EntryStatus column
                    sheet.update_cell(i, 5, now)        # EntryTime column
                    st.success(f"🎉 **WELCOME TO NREC!**")
                    st.success(f"✅ **Entry recorded** for **{row['Name']}**")
                    st.info(f"📚 **Branch:** {row['Branch']}")
                    st.info(f"🕐 **Entry Time:** {now}")
                    st.balloons()
                    
                    # Show welcome message
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                color: white; padding: 20px; border-radius: 15px; 
                                text-align: center; margin: 20px 0;">
                        <h3>🎓 Welcome to Orientation Day!</h3>
                        <p>Your entry has been successfully recorded.</p>
                        <p><strong>Next:</strong> Proceed to the orientation hall</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                # Already entered
                else:
                    st.warning(f"⚠️ **{row['Name']}** has already checked in!")
                    st.info(f"📅 **Previous Entry Time:** {row.get('EntryTime', 'Not recorded')}")
                    st.info("✅ You're all set! Proceed to the orientation activities.")
                
                break
        
        if not found:
            st.error("❌ **Student ID not found** in orientation records.")
            st.write("Please verify your QR code or contact the registration desk.")
            
    except Exception as e:
        st.error(f"**Database Error:** {e}")
        st.write("Please try again or contact technical support.")

# ========================
# STREAMLIT UI
# ========================

def main():
    st.set_page_config(
        page_title="NREC Entry Scanner", 
        page_icon="🚪", 
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #4CAF50;
        font-size: 3rem;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    .college-header {
        text-align: center;
        color: #2196F3;
        font-size: 1.5rem;
        margin-bottom: 1rem;
        font-style: italic;
    }
    .entry-banner {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .instruction-box {
        background-color: #e8f5e8;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4CAF50;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<h1 class="main-header">🚪 ENTRY SCANNER</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="college-header">Narsimha Reddy Engineering College</h2>', unsafe_allow_html=True)
    
    # Entry Banner
    st.markdown("""
    <div class="entry-banner">
        <h2>🎓 ORIENTATION DAY CHECK-IN</h2>
        <h3>📅 August 18th, 2025</h3>
        <p><strong>Welcome Students!</strong> Scan your QR code to check-in for orientation.</p>
        <p>🚪 <strong>This station is for ENTRY ONLY</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="instruction-box">
    📌 <strong>Entry Instructions:</strong><br>
    1. <strong>Scan your student QR code</strong> to check-in<br>
    2. Wait for confirmation message<br>
    3. Proceed to the orientation hall<br>
    4. Keep your student ID ready for verification<br>
    5. For exit, use the <strong>EXIT SCANNER</strong> at the other station
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize Google Sheets
    if not GSPREAD_AVAILABLE:
        st.error("❌ **Google Sheets integration not available**")
        st.info("To enable Google Sheets functionality, please ensure these packages are installed:")
        st.code("pip install gspread oauth2client")
        st.stop()
    
    sheet = init_google_sheets()
    if not sheet:
        st.stop()
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📱 QR Camera Scanner", "📝 Manual Entry"])
    
    with tab1:
        st.write("### 📱 Camera QR Scanner")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Primary Camera Scanner
            st.write("#### 📷 Scan Student QR Code")
            camera_image = st.camera_input(
                "Point camera at student's QR code and take photo",
                help="For best results: ensure good lighting, hold steady, QR code fills frame"
            )
            
            if camera_image:
                img = Image.open(camera_image)
                st.image(img, caption="📸 Captured QR Code", width=400)
                
                with st.spinner("🔍 Processing entry..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned Student ID:** {qr_data}")
                    process_student_entry(qr_data, sheet)
                else:
                    st.error("⚠️ **No QR code detected** in the image.")
                    st.write("**Try again with:**")
                    st.write("• Better lighting")
                    st.write("• QR code fully visible in frame")
                    st.write("• Hold camera steady")
        
        with col2:
            # Entry Status
            st.write("#### 🚪 Entry Status")
            
            if not camera_image:
                st.info("📷 **Ready for check-in**\nScan QR code to record entry")
            
            # Alternative upload option
            st.write("---")
            st.write("#### 📤 Upload QR Image")
            uploaded_file = st.file_uploader(
                "Upload QR Code Photo", 
                type=['png', 'jpg', 'jpeg'],
                help="Upload a clear photo of the QR code"
            )
            
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, caption="Uploaded QR Code", width=300)
                
                with st.spinner("🔍 Processing entry..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned ID:** {qr_data}")
                    process_student_entry(qr_data, sheet)
                else:
                    st.error("⚠️ No QR code detected in uploaded image.")

    with tab2:
        st.write("### 📝 Manual Student ID Entry")
        st.info("Use this option if camera scanning is not available.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("#### ✏️ Enter Student ID")
            manual_id = st.text_input(
                "Student ID:", 
                placeholder="e.g., 2025001",
                help="Enter the student ID exactly as shown on the ID card"
            )
            
            if st.button("🚪 Process Entry", type="primary", use_container_width=True):
                if manual_id.strip():
                    process_student_entry(manual_id.strip(), sheet)
                else:
                    st.warning("⚠️ Please enter a valid Student ID.")
        
        with col2:
            st.write("#### 📊 Entry Guidelines")
            st.success("""
            **✅ When to use Manual Entry:**
            • Camera not working
            • QR code damaged/unreadable
            • Student forgot QR code
            • Technical issues
            """)
    
    # Entry Statistics
    st.write("---")
    st.write("#### 📈 Today's Entry Stats")
    
    # Get real-time statistics
    stats = get_entry_statistics(sheet)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🟢 Total Entries", stats["total_entries"], help="Students checked in today")
    
    with col2:
        st.metric("👥 Currently Present", stats["currently_present"], help="Students currently inside")
    
    with col3:
        st.metric("📊 Total Students", stats["total_students"], help="Total registered students")
    
    # Additional info
    col1, col2 = st.columns(2)
    with col1:
        st.metric("⏰ Current Time", datetime.now().strftime("%H:%M:%S"))
    with col2:
        st.metric("📅 Date", datetime.now().strftime("%Y-%m-%d"))
    
    # Important Notice
    st.markdown("---")
    st.error("""
    **🔄 Important:** This is the **ENTRY ONLY** station. 
    For exit or food tracking, please use the **EXIT/FOOD SCANNER** at the designated station.
    """)
    
    # Footer
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
        <h4>🚪 Entry Scanner Station</h4>
        <p><strong>NREC Orientation Day - August 18th, 2025</strong></p>
        <p style="font-size: 12px; margin-top: 15px;">
            © 2025 NRCM - Entry Management System
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()