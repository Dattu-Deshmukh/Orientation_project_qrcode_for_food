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
    """Initialize Google Sheets connection using st.secrets only"""
    if not GSPREAD_AVAILABLE:
        st.error("Google Sheets integration not available. Please install required packages.")
        return None
        
    try:
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        
        # Load credentials from Streamlit secrets only
        if "gcp_service_account" not in st.secrets:
            st.error("❌ **Google Sheets credentials not found in Streamlit secrets!**")
            st.info("""
            **Setup Instructions:**
            1. Go to Streamlit Cloud → Your App → Settings → Secrets
            2. Add your service account JSON under key `gcp_service_account`
            3. Redeploy your app
            """)
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        sheet = client.open("orientation_passes").sheet1
        return sheet
        
    except FileNotFoundError as e:
        st.error("❌ **Google Sheet 'orientation_passes' not found!**")
        st.info("Please ensure your Google Sheet is named exactly 'orientation_passes' and shared with the service account.")
        return None
        
    except Exception as e:
        st.error(f"❌ **Failed to connect to Google Sheets:** {e}")
        st.info("""
        **Troubleshooting:**
        1. Verify service account JSON is correctly added to Streamlit secrets
        2. Ensure Google Sheet is named 'orientation_passes'
        3. Share the sheet with your service account email
        4. Enable Google Sheets API and Google Drive API
        """)
        return None

def get_exit_statistics(sheet):
    """Get real-time exit statistics"""
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

def process_student_exit(qr_data, sheet):
    """Process the scanned student data for EXIT ONLY"""
    try:
        records = sheet.get_all_records()
        found = False
        
        for i, row in enumerate(records, start=2):
            if str(row["ID"]) == str(qr_data):
                found = True
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Check if student has entered
                entry_status = row.get("EntryStatus", "")
                
                if not entry_status:
                    st.error(f"❌ **{row['Name']}** hasn't checked in yet!")
                    st.info("Please check-in at the ENTRY SCANNER first.")
                    return
                
                # Handle EXIT only
                exit_status = row.get("ExitStatus", "")
                
                if not exit_status or exit_status == "":
                    sheet.update_cell(i, 6, "Exited")   # ExitStatus column
                    sheet.update_cell(i, 7, now)        # ExitTime column
                    st.success(f"👋 **Thank you for attending!**")
                    st.success(f"🚪 **Exit recorded** for **{row['Name']}**")
                    st.info(f"📚 **Branch:** {row['Branch']}")
                    st.info(f"🕐 **Exit Time:** {now}")
                    
                    # Calculate duration if entry time exists
                    entry_time = row.get("EntryTime", "")
                    if entry_time:
                        try:
                            entry_dt = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
                            exit_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
                            duration = exit_dt - entry_dt
                            hours = duration.total_seconds() // 3600
                            minutes = (duration.total_seconds() % 3600) // 60
                            st.info(f"⏱️ **Total Duration:** {int(hours)}h {int(minutes)}m")
                        except:
                            pass
                    
                    # Show goodbye message
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #ff7b7b 0%, #667eea 100%); 
                                color: white; padding: 20px; border-radius: 15px; 
                                text-align: center; margin: 20px 0;">
                        <h3>🎓 Thank You for Attending!</h3>
                        <p>Your exit has been successfully recorded.</p>
                        <p><strong>Safe journey home!</strong></p>
                        <p>We hope you enjoyed the orientation program.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.warning(f"⚠️ **{row['Name']}** has already checked out!")
                    st.info(f"📅 **Previous Exit Time:** {row.get('ExitTime', 'Not recorded')}")
                    st.info("✅ Exit was already recorded. Safe journey!")
                
                break
        
        if not found:
            st.error("❌ **Student ID not found** in records.")
            st.write("Please verify the QR code or contact the administrator.")
            
    except Exception as e:
        st.error(f"**Database Error:** {e}")
        st.write("Please try again or contact technical support.")

# ========================
# STREAMLIT UI
# ========================

def main():
    st.set_page_config(
        page_title="NREC Exit Scanner", 
        page_icon="🚪", 
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #FF5722;
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
    .exit-banner {
        background: linear-gradient(135deg, #FF5722 0%, #E91E63 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .instruction-box {
        background-color: #ffebee;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #FF5722;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<h1 class="main-header">🚪 EXIT SCANNER</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="college-header">Narsimha Reddy Engineering College</h2>', unsafe_allow_html=True)
    
    # Exit Banner
    st.markdown("""
    <div class="exit-banner">
        <h2>👋 ORIENTATION DAY CHECK-OUT</h2>
        <h3>📅 August 18th, 2025</h3>
        <p><strong>Thank You for Attending!</strong> Scan your QR code to check-out.</p>
        <p>🚪 <strong>This station is for EXIT ONLY</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="instruction-box">
    📌 <strong>Exit Instructions:</strong><br>
    1. <strong>Scan your student QR code</strong> to check-out<br>
    2. Wait for confirmation message<br>
    3. Thank you for attending orientation<br>
    4. Safe journey home!<br>
    5. For entry, use the <strong>ENTRY SCANNER</strong> at the main entrance
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize Google Sheets
    if not GSPREAD_AVAILABLE:
        st.error("❌ **Google Sheets integration not available**")
        st.info("To enable Google Sheets functionality, please install required packages:")
        st.code("pip install gspread oauth2client")
        st.info("**For Streamlit Cloud:** Add these to your requirements.txt file")
        st.stop()
    
    sheet = init_google_sheets()
    if not sheet:
        st.error("🔧 **Unable to connect to Google Sheets**")
        st.info("""
        **For Streamlit Cloud Setup:**
        1. Go to your app dashboard
        2. Click Settings → Secrets
        3. Add your service account JSON under `gcp_service_account`
        4. Redeploy the app
        
        **Service Account Setup:**
        - Enable Google Sheets API and Google Drive API
        - Share 'orientation_passes' sheet with service account email
        - Ensure proper JSON format in secrets
        """)
        st.stop()
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📱 QR Camera Scanner", "📝 Manual Entry"])
    
    with tab1:
        st.write("### 📱 Camera QR Scanner")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Primary Camera Scanner
            st.write("#### 📷 Scan Student QR Code for Exit")
            camera_image = st.camera_input(
                "Point camera at student's QR code and take photo",
                help="Scan when student is leaving the orientation"
            )
            
            if camera_image:
                img = Image.open(camera_image)
                st.image(img, caption="📸 Captured QR Code", width=400)
                
                with st.spinner("🔍 Processing exit..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned Student ID:** {qr_data}")
                    process_student_exit(qr_data, sheet)
                else:
                    st.error("⚠️ **No QR code detected** in the image.")
                    st.write("**Try again with:**")
                    st.write("• Better lighting")
                    st.write("• QR code fully visible in frame")
                    st.write("• Hold camera steady")
        
        with col2:
            # Exit Status
            st.write("#### 🚪 Exit Status")
            
            if not camera_image:
                st.info("📷 **Ready for check-out**\nScan QR code to record exit")
            
            st.write("#### 🚪 Exit Process")
            st.success("""
            **✅ Exit Requirements:**
            • Must have checked-in first
            • Valid student QR code
            • Clear scan image
            • Complete orientation attendance
            """)
            
            st.info("""
            **📋 What happens on exit:**
            • Records exit time
            • Calculates total duration
            • Shows thank you message
            • Updates attendance records
            """)
            
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
                
                with st.spinner("🔍 Processing exit..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned ID:** {qr_data}")
                    process_student_exit(qr_data, sheet)
                else:
                    st.error("⚠️ No QR code detected in uploaded image.")

    with tab2:
        st.write("### 📝 Manual Student ID Entry")
        st.info("Use this option if camera scanning is not available.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("#### ✏️ Enter Student ID for Exit")
            manual_id = st.text_input(
                "Student ID:", 
                placeholder="e.g., 2025001",
                help="Enter the student ID exactly as shown on the ID card"
            )
            
            if st.button("🚪 Process Exit", type="primary", use_container_width=True):
                if manual_id.strip():
                    process_student_exit(manual_id.strip(), sheet)
                else:
                    st.warning("⚠️ Please enter a valid Student ID.")
        
        with col2:
            st.write("#### 📊 Manual Exit Guidelines")
            st.success("""
            **✅ When to use Manual Entry:**
            • Camera not working
            • QR code damaged/unreadable
            • Student forgot QR code
            • Technical issues
            • Emergency situations
            """)
            
            st.warning("""
            **⚠️ Exit Verification:**
            • Verify student identity
            • Check entry status first
            • Confirm orientation completion
            • Record any special notes
            """)
    
    # Exit Statistics
    st.write("---")
    st.write("#### 📈 Today's Exit Stats")
    
    # Get real-time statistics
    stats = get_exit_statistics(sheet)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🚪 Total Exits", stats["total_exits"], help="Students who have left")
    
    with col2:
        st.metric("👥 Still Present", stats["currently_present"], help="Students still inside")
    
    with col3:
        st.metric("🟢 Total Entries", stats["total_entries"], help="Students who entered today")
    
    with col4:
        st.metric("📊 Total Students", stats["total_students"], help="Total registered students")
    
    # Additional info
    col1, col2 = st.columns(2)
    with col1:
        st.metric("⏰ Current Time", datetime.now().strftime("%H:%M:%S"))
    with col2:
        st.metric("📅 Date", datetime.now().strftime("%Y-%m-%d"))
    
    # Exit Information
    st.write("---")
    st.write("#### 🎓 Exit Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""
        **🚪 Exit Process:**
        • Student scans QR for checkout
        • System records exit time
        • Calculates attendance duration
        • Shows thank you message
        • Updates final attendance
        """)
        
    with col2:
        st.success("""
        **✅ Completed Orientation:**
        • Welcome session attended
        • Campus tour completed
        • Department introduction done
        • Student activities explored
        • All requirements met
        """)
    
    # Important Notice
    st.markdown("---")
    st.error("""
    **🔄 Important:** This is the **EXIT ONLY** station. 
    For entry check-in, please use the **ENTRY SCANNER** at the main entrance.
    """)
    
    # Emergency Contact
    st.warning("""
    **🆘 Need Help?**
    Contact Exit Station Manager: **+91-XXXX-XXXXXX** | Email: **exit@nrec.edu.in**
    """)
    
    # Footer
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
        <h4>🚪 Exit Scanner Station</h4>
        <p><strong>NREC Orientation Day - August 18th, 2025</strong></p>
        <p style="font-size: 12px; margin-top: 15px;">
            © 2025 NRCM - Exit Management System
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()