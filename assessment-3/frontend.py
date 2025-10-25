import streamlit as st
import requests
import os
from streamlit_autorefresh import st_autorefresh

BASE_URL = "http://n10893997.cab432.com:3000"
st.title("CAB432 A2 Frontend - Video File Transcoder")

# ---------------- SESSION STATE ----------------
if "token" not in st.session_state: st.session_state["token"] = None        # ID token
if "access_token" not in st.session_state: st.session_state["access_token"] = None  # Access token
if "username" not in st.session_state: st.session_state["username"] = None
if "search_results" not in st.session_state: st.session_state["search_results"] = []
if "selected_metadata" not in st.session_state: st.session_state["selected_metadata"] = None
if "show_metadata_modal" not in st.session_state: st.session_state["show_metadata_modal"] = False
if "pending_challenge" not in st.session_state: st.session_state["pending_challenge"] = None
if "current_page" not in st.session_state: st.session_state["current_page"] = 1
if "mfa_qr" not in st.session_state: st.session_state["mfa_qr"] = None      # MFA QR persistence

# ---------------- AUTH ----------------
st.header("Authentication")
if not st.session_state["token"]:
    # MFA challenge flow
    if st.session_state["pending_challenge"] and st.session_state["pending_challenge"]["type"] == "MFA":
        code = st.text_input("Enter MFA Code")
        if st.button("Submit Code"):
            challenge = st.session_state["pending_challenge"]
            res2 = requests.post(f"{BASE_URL}/auth/respond-mfa", json={
                "username": challenge["username"],
                "session": challenge["session"],
                "code": code
            })
            if res2.status_code == 200:
                data = res2.json()
                st.session_state["token"] = data["id_token"]
                st.session_state["access_token"] = data["access_token"]
                st.session_state["username"] = challenge["username"]
                st.session_state["pending_challenge"] = None
                st.success("MFA login successful")
                st.rerun()
            else:
                st.error(res2.text)

    # New password challenge flow
    elif st.session_state["pending_challenge"] and st.session_state["pending_challenge"]["type"] == "NEW_PASSWORD":
        st.warning("You must set a new permanent password.")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Set New Password"):
            challenge = st.session_state["pending_challenge"]
            res2 = requests.post(
                f"{BASE_URL}/auth/complete-new-password",
                json={"username": challenge["username"], "new_password": new_pass, "session": challenge["session"]},
            )
            if res2.status_code == 200:
                token_data = res2.json()
                st.session_state["token"] = token_data["id_token"]
                st.session_state["access_token"] = token_data["access_token"]
                st.session_state["username"] = challenge["username"]
                st.session_state["pending_challenge"] = None
                st.success("Password updated and logged in!")
                st.rerun()
            else:
                st.error(f"Password update failed: {res2.text}")

    # Normal login/signup flow
    else:
        auth_mode = st.radio("Choose action", ["Login", "Signup"], horizontal=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if auth_mode == "Signup":
            email = st.text_input("Email")
            if st.button("Sign up"):
                res = requests.post(f"{BASE_URL}/auth/signup", json={"username": username, "email": email, "password": password})
                if res.status_code == 200: st.success("Signup successful! Check email for confirmation code.")
                else: st.error(f"Signup failed: {res.text}")
            code = st.text_input("Confirmation Code (from email)")
            if st.button("Confirm Signup"):
                res = requests.post(f"{BASE_URL}/auth/confirm", json={"username": username, "code": code})
                if res.status_code == 200: st.success("Account confirmed. You can log in.")
                else: st.error(f"Confirmation failed: {res.text}")
        else:
            if st.button("Login"):
                res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})

                # Debug logs
                st.write("DEBUG raw login response:", res.text)
                if res.headers.get("content-type") == "application/json":
                    try:
                        st.write("DEBUG parsed login JSON:", res.json())
                    except Exception as e:
                        st.write("DEBUG error parsing JSON:", str(e))

                if res.status_code == 200:
                    data = res.json()
                    if "id_token" in data and "access_token" in data:
                        st.session_state["token"] = data["id_token"]
                        st.session_state["access_token"] = data["access_token"]
                        st.session_state["username"] = username
                        st.success("Logged in successfully")
                        st.rerun()
                    elif data.get("challenge") == "NEW_PASSWORD_REQUIRED":
                        st.session_state["pending_challenge"] = {"username": username, "session": data["session"], "type": "NEW_PASSWORD"}
                        st.warning("You must set a new permanent password.")
                        st.rerun()
                    elif data.get("challenge") == "SOFTWARE_TOKEN_MFA":
                        st.session_state["pending_challenge"] = {"username": username, "session": data["session"], "type": "MFA"}
                        st.warning("Enter your MFA code to continue.")
                        st.rerun()
                    else:
                        st.error("Unexpected login response")
                else: st.error(f"Login failed: {res.text}")
else:
    # ---------------- LOGGED IN ----------------
    st.success(f"Logged in as {st.session_state['username']}")

    if st.button("Logout"):
        for key in ["token","access_token","username","search_results",
                    "selected_metadata","show_metadata_modal","pending_challenge","mfa_qr"]:
            st.session_state[key] = None
        st.session_state["current_page"] = 1
        st.rerun()

    # ---------------- MFA SETUP ----------------
    st.subheader("Multi-Factor Authentication (MFA)")

    if st.session_state.get("mfa_qr"):
        st.image(st.session_state["mfa_qr"])
        mfa_code = st.text_input("Enter 6-digit code from Authenticator")
        if st.button("Verify MFA"):
            res2 = requests.post(
                f"{BASE_URL}/auth/verify-mfa",
                json={"access_token": st.session_state["access_token"], "code": mfa_code}
            )
            if res2.status_code == 200:
                st.success("MFA verified successfully. Next login will require the code.")
                st.session_state["mfa_qr"] = None
            else:
                st.error(res2.text)

    if st.button("Setup MFA"):
        res = requests.post(f"{BASE_URL}/auth/setup-mfa", json={"access_token": st.session_state["access_token"]})
        if res.status_code == 200:
            data = res.json()
            st.session_state["mfa_qr"] = data["qr_code"]
            st.rerun()
        else:
            st.error(res.text)

# ---------------- AUTH HEADERS ----------------
token = st.session_state.get("token", None)
headers = {"Authorization": f"Bearer {token}"} if token else {}

# ---------------- MAIN APP ----------------
if token:
    st_autorefresh(interval=5000, key="queue_refresh")

    # ---------------- UPLOAD ----------------
    st.header("Upload a Video to Queue")
    uploaded_file = st.file_uploader("Choose a video", type=["mp4", "mov", "avi"])
    imdb_id = st.text_input("IMDb ID (optional)")
    if st.button("Add to Queue"):
        if uploaded_file:
            res = requests.post(f"{BASE_URL}/upload-url", params={"filename": uploaded_file.name}, headers=headers)
            if res.status_code == 200:
                data = res.json()
                upload_url = data["upload_url"]
                s3_key = data["s3_key"]
                file_id = data["file_id"]

                put_res = requests.put(upload_url, data=uploaded_file.getvalue())
                if put_res.status_code == 200:
                    confirm = requests.post(
                        f"{BASE_URL}/confirm-upload",
                        params={"file_id": file_id, "s3_key": s3_key, "filename": uploaded_file.name, "imdbID": imdb_id},
                        headers=headers
                    )
                    if confirm.status_code == 200:
                        st.success("File uploaded and metadata saved!")
                        st.rerun()
                    else:
                        st.error(f"Metadata save failed: {confirm.text}")
                else:
                    st.error(f"S3 upload failed: {put_res.text}")
            else:
                st.error(f"Could not get upload URL: {res.text}")
        else:
            st.warning("Please select a file before adding to queue.")

    # ---------------- JOB QUEUE ----------------
    st.header("Job Queue")
    res = requests.get(f"{BASE_URL}/jobs", headers=headers)
    if res.status_code == 200:
        jobs = res.json().get("jobs", [])
        active_jobs = [job for job in jobs if job.get("status", "").lower() != "completed"]

        if not active_jobs:
            st.info("No active jobs. Upload files to add to the queue.")
        else:
            header_cols = st.columns([2, 3, 5, 3, 3, 2])
            header_cols[0].markdown("**#**")
            header_cols[1].markdown("**Owner**")
            header_cols[2].markdown("**File Name**")
            header_cols[3].markdown("**Status**")
            header_cols[4].markdown("**Details**")
            header_cols[5].markdown("**Delete**")
            for idx, job in enumerate(active_jobs, start=1):
                cols = st.columns([2, 3, 5, 3, 3, 2])
                cols[0].write(idx)
                cols[1].write(job.get("qut-username", st.session_state["username"]))
                cols[2].write(job.get("filename", "N/A"))
                status = job.get("status", "unknown").lower()
                if status == "queued": cols[3].write("🟡 Queued")
                elif status == "processing": cols[3].write("🟠 Processing")
                elif status == "failed": cols[3].write("🔴 Error")
                else: cols[3].write(status)
                if job.get("jobs_id"):
                    if cols[4].button("Details", key=f"dt_{job['jobs_id']}"):
                        st.session_state["selected_metadata"] = job
                        st.session_state["show_metadata_modal"] = True
                    if cols[5].button("🗑️", key=f"del_{job['jobs_id']}"):
                        res2 = requests.delete(f"{BASE_URL}/jobs/{job['jobs_id']}", headers=headers)
                        if res2.status_code == 200: st.success("Job deleted"); st.rerun()
                        else: st.error("Delete failed")

    # ---------------- START TRANSCODING ----------------
    if st.button("Start Transcoding Jobs"):
        res = requests.post(f"{BASE_URL}/jobs/start", headers=headers)
        if res.status_code == 200:
            data = res.json()
            st.success(f"Started {len(data['jobs'])} job(s)")
            st.rerun()
        else:
            st.error(f"Failed to start jobs: {res.status_code} - {res.text}")

    # ---------------- METADATA MODAL ----------------
    if st.session_state.get("show_metadata_modal") and st.session_state.get("selected_metadata"):
        @st.dialog("File & Movie Metadata")
        def show_modal():
            meta = st.session_state["selected_metadata"]
            st.write(f"**Filename:** {meta.get('filename','Unknown')}")
            if meta.get("imdbID"): st.write(f"🎬 IMDb ID: {meta.get('imdbID')}")
            if st.button("Close"):
                st.session_state["show_metadata_modal"] = False
                st.rerun()
        show_modal()

    # ---------------- ALL JOBS ----------------
    st.header("All Jobs")
    res = requests.get(f"{BASE_URL}/jobs", headers=headers)
    if res.status_code == 200:
        backend_jobs = res.json().get("jobs", [])
        if backend_jobs:
            st.subheader("Filters & Sorting")
            owner_filter = st.text_input("Filter by Owner:", "")
            formats = sorted(list({os.path.splitext(job["filename"])[1] for job in backend_jobs if job.get("filename")}))
            format_filter = st.multiselect("Filter by format", formats, default=formats)
            statuses = ["queued", "processing", "completed", "failed"]
            status_filter = st.multiselect("Filter by status", statuses, default=statuses)
            sort_option = st.selectbox("Sort by", ["Created Date (Newest)", "Created Date (Oldest)", "File Name A-Z", "File Name Z-A"])

            filtered_jobs = []
            for job in backend_jobs:
                ext = os.path.splitext(job["filename"])[1] if job.get("filename") else ""
                status = job.get("status", "").lower()
                owner = job.get("qut-username", "")
                include = True
                if owner_filter and owner_filter.lower() not in owner.lower(): include = False
                if ext not in format_filter: include = False
                if status not in status_filter: include = False
                if include: filtered_jobs.append(job)

            if sort_option == "File Name A-Z": filtered_jobs.sort(key=lambda x: x.get("filename", "").lower())
            elif sort_option == "File Name Z-A": filtered_jobs.sort(key=lambda x: x.get("filename", "").lower(), reverse=True)
            elif sort_option == "Created Date (Newest)": filtered_jobs.sort(key=lambda x: x.get("created", ""), reverse=True)
            elif sort_option == "Created Date (Oldest)": filtered_jobs.sort(key=lambda x: x.get("created", ""))

            page_size = st.number_input("Jobs per page", min_value=1, max_value=100, value=10, step=1)
            total_jobs = len(filtered_jobs)
            total_pages = (total_jobs + page_size - 1) // page_size
            current_page = st.session_state.get("current_page") or 1

            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ Previous") and current_page > 1:
                    st.session_state["current_page"] = current_page - 1
            with col_page: st.write(f"Page {current_page} of {total_pages}")
            with col_next:
                if st.button("Next ➡️") and current_page < total_pages:
                    st.session_state["current_page"] = current_page + 1

            start_idx = (current_page - 1) * page_size
            end_idx = start_idx + page_size
            jobs_to_display = filtered_jobs[start_idx:end_idx]

            header_cols = st.columns([3, 2, 2, 2, 2])
            header_cols[0].markdown("**File Name**")
            header_cols[1].markdown("**Owner**")
            header_cols[2].markdown("**Created At**")
            header_cols[3].markdown("**Status**")
            header_cols[4].markdown("**Download**")

            for job in jobs_to_display:
                cols = st.columns([3, 2, 2, 2, 2, 2])
                cols[0].write(job.get("filename", "N/A"))
                cols[1].write(job.get("qut-username", "N/A"))
                cols[2].write(job.get("created", "N/A"))
                status = job.get("status", "")
                if status == "queued": cols[3].write("🟡 Queued")
                elif status == "processing": cols[3].write("🟠 Processing")
                elif status == "completed": cols[3].write("🟢 Done")
                elif status == "failed": cols[3].write("🔴 Error")
                else: cols[3].write(status)

                if status == "completed":
                    if cols[4].button("Download", key=f"dl_{job['jobs_id']}"):
                        dl_res = requests.get(f"{BASE_URL}/download/{job['jobs_id']}", headers=headers)
                        if dl_res.status_code == 200:
                            download_url = dl_res.json().get("download_url")
                            if download_url:
                                st.markdown(f"[Click here to download your file]({download_url})", unsafe_allow_html=True)
                            else:
                                st.error("No download URL returned")
                        else:
                            st.error("Download failed")
                else:
                    cols[4].button("Not Ready", key=f"nr_{job['jobs_id']}", disabled=True)

                if cols[5].button("🗑️", key=f"adel_{job['jobs_id']}"):
                    res2 = requests.delete(f"{BASE_URL}/jobs/{job['jobs_id']}", headers=headers)
                    if res2.status_code == 200:
                        st.success("Job deleted")
                        st.rerun()
                    else:
                        st.error("Delete failed")
