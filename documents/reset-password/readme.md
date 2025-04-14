# SharFund JWT Password Reset APIs

This document provides a guide for integrating the SharFund password reset APIs in a React frontend using Axios. The APIs include forget password, OTP verification, and password reset, enabling users to recover their accounts securely. Tailored for frontend developers new to backend integration, this guide covers essential steps to make API requests, handle responses, and manage common issues like CORS and CSRF, without requiring deep backend knowledge.

## Overview

- **Base URL**: `http://127.0.0.1:7877` (development server; replace with production URL as needed).
- **Content-Type**: `application/json` for all requests.
- **Authentication**: All endpoints are public (no authentication required).
- **CORS**: Configured to allow requests from `http://localhost:3000`.
- **Flow**: 
  1. Request an OTP (`/api/v1/forget-password/`).
  2. Verify the OTP (`/api/v1/verify-otp/`).
  3. Reset the password (`/api/v1/reset-password/`), which requires a valid OTP.

## APIs

### 1. Forget Password (`POST /api/v1/forget-password/`)

#### Purpose
Initiates the password reset process by sending a 6-digit OTP to the user’s email if the email is registered.

#### Request Format
| Field   | Type   | Required | Description                                      |
|---------|--------|----------|--------------------------------------------------|
| `email` | String | Yes      | User’s email (e.g., `user3@example.com`).        |

**Example Payload**:
```json
{
    "email": "user3@example.com"
}
```

#### Response Format
- **Success (HTTP 200 OK)**:
  ```json
  {
      "message": "OTP sent to your email."
  }
  ```
  - Sends an email with the OTP, username (e.g., `ugr_2025_3`), and email in a styled template (coffee-colored background, golden-white gradient text, logo).
- **Error (HTTP 400 Bad Request)**:
  ```json
  {
      "errors": {
          "email": ["Email ID doesn't exist."]
      }
  }
  ```

#### Integration Notes
- Trigger this from a “Forgot Password?” link or form in your UI.
- On success, display a message (e.g., “Check your email for the OTP”) and show an OTP input field.
- If `error.errors.email` is returned, inform the user the email isn’t registered and suggest signing up.

### 2. Verify OTP (`POST /api/v1/verify-otp/`)

#### Purpose
Verifies the OTP sent to the user’s email, allowing progression to password reset if correct and not expired.

#### Request Format
| Field   | Type   | Required | Description                                      |
|---------|--------|----------|--------------------------------------------------|
| `email` | String | Yes      | User’s email (e.g., `user3@example.com`).        |
| `otp`   | String | Yes      | 6-digit OTP received via email (e.g., `123456`). |

**Example Payload**:
```json
{
    "email": "user3@example.com",
    "otp": "123456"
}
```

#### Response Format
- **Success (HTTP 200 OK)**:
  ```json
  {
      "message": "OTP is Correct"
  }
  ```
- **Error (HTTP 400 Bad Request)**:
  ```json
  {
      "errors": {
          "otp": ["Invalid OTP."],
          "otp": ["OTP has expired."],
          "email": ["Email ID doesn't exist."]
      }
  }
  ```

#### Integration Notes
- Call this after the user enters the OTP in your form.
- On success, display a password reset form with fields for `create_password` and `confirm_password`.
- Handle errors:
  - `error.errors.otp`: Show “Invalid OTP” or “OTP has expired” and prompt to request a new OTP via `/api/v1/forget-password/`.
  - `error.errors.email`: Inform the user the email isn’t valid.

### 3. Reset Password (`POST /api/v1/reset-password/`)

#### Purpose
Resets the user’s password after OTP verification, requiring a valid, non-expired OTP and matching passwords.

#### Request Format
| Field              | Type   | Required | Description                                      |
|--------------------|--------|----------|--------------------------------------------------|
| `email`            | String | Yes      | User’s email (e.g., `user3@example.com`).        |
| `create_password`  | String | Yes      | New password (min 8 chars, e.g., `newpassword123`). |
| `confirm_password` | String | Yes      | Must match `create_password`.                    |

**Example Payload**:
```json
{
    "email": "user3@example.com",
    "create_password": "newpassword123",
    "confirm_password": "newpassword123"
}
```

#### Response Format
- **Success (HTTP 200 OK)**:
  ```json
  {
      "message": "Password changed successfully"
  }
  ```
- **Error (HTTP 400 Bad Request)**:
  ```json
  {
      "errors": {
          "email": ["Email ID doesn't exist."],
          "confirm_password": ["Passwords do not match."],
          "create_password": ["Password must be at least 8 characters long."],
          "general": ["No valid OTP found. Please request a new OTP."],
          "general": ["OTP has expired. Please request a new OTP."]
      }
  }
  ```

#### Integration Notes
- Call this only after `/api/v1/verify-otp/` returns “OTP is Correct”.
- The endpoint checks for a valid OTP (generated by `/api/v1/forget-password/`, not expired).
- On success, show a success message (e.g., “Password reset! Please log in”) and redirect to the login page.
- Handle errors:
  - `error.errors.confirm_password` or `error.errors.create_password`: Display next to form inputs.
  - `error.errors.email`: Prompt to restart the process.
  - `error.errors.general`: If OTP is missing or expired, redirect to `/api/v1/forget-password/`.

## Integration Steps for React with Axios

### 1. Install Axios
Ensure Axios is installed in your React project:
```bash
npm install axios
```

### 2. Make API Requests
Send `POST` requests with `withCredentials: true` for consistency, even though these endpoints don’t set cookies.

**Example (Generic Function)**:
```javascript
import axios from 'axios';

const apiRequest = async (endpoint, data) => {
    try {
        const response = await axios.post(
            `http://127.0.0.1:7877${endpoint}`,
            data,
            {
                headers: { 'Content-Type': 'application/json' },
                withCredentials: true
            }
        );
        return response.data;
    } catch (error) {
        throw error.response.data;
    }
};

// Usage examples
// Forget Password
apiRequest('/api/v1/forget-password/', {
    email: 'user3@example.com'
})
    .then(data => console.log('OTP Request:', data))
    .catch(error => console.error('Error:', error));

// Verify OTP
apiRequest('/api/v1/verify-otp/', {
    email: 'user3@example.com',
    otp: '123456'
})
    .then(data => console.log('OTP Verify:', data))
    .catch(error => console.error('Error:', error));

// Reset Password
apiRequest('/api/v1/reset-password/', {
    email: 'user3@example.com',
    create_password: 'newpassword123',
    confirm_password: 'newpassword123'
})
    .then(data => console.log('Reset Password:', data))
    .catch(error => console.error('Error:', error));
```

### 3. Handle Cookies
- These endpoints do not set cookies, unlike registration/login.
- Use `withCredentials: true` to align with other APIs and avoid CORS issues.
- No cookie verification is needed here, but check Developer Tools if testing alongside other endpoints.

### 4. Handle Responses
- **Success**:
  - Use `data.message`:
    - Forget Password: Show “Check your email for the OTP”.
    - Verify OTP: Show password reset form.
    - Reset Password: Show “Password reset successfully” and redirect to login.
- **Error**:
  - Parse `error.errors`:
    - Field-specific (e.g., `errors.email`, `errors.otp`, `errors.confirm_password`): Display next to inputs.
    - General (e.g., `errors.general`): Show as alerts (e.g., “OTP has expired”).
  - Example: For `errors.general` like “No valid OTP found”, prompt to restart with `/api/v1/forget-password/`.

### 5. CORS Considerations
- APIs allow requests from `http://localhost:3000`. Ensure your React app runs on this origin.
- Always include `withCredentials: true` to maintain consistency.

### 6. CSRF Protection
- If 403 errors occur, the API may require a CSRF token:
  - Fetch the `csrftoken` cookie or a CSRF endpoint.
  - Configure Axios:
    ```javascript
    axios.defaults.xsrfCookieName = 'csrftoken';
    axios.defaults.xsrfHeaderName = 'X-CSRFToken';
    ```

## Testing the APIs

### cURL Commands
- **Forget Password**:
  ```bash
  curl -X POST http://127.0.0.1:7877/api/v1/forget-password/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"email":"user3@example.com"}'
  ```
- **Verify OTP**:
  ```bash
  curl -X POST http://127.0.0.1:7877/api/v1/verify-otp/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"email":"user3@example.com","otp":"123456"}'
  ```
- **Reset Password**:
  ```bash
  curl -X POST http://127.0.0.1:7877/api/v1/reset-password/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"email":"user3@example.com","create_password":"newpassword123","confirm_password":"newpassword123"}'
  ```

### PowerShell Commands
- **Forget Password**:
  ```powershell
  Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/forget-password/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"email":"user3@example.com"}'
  ```
- **Verify OTP**:
  ```powershell
  Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/verify-otp/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"email":"user3@example.com","otp":"123456"}'
  ```
- **Reset Password**:
  ```powershell
  Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/reset-password/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"email":"user3@example.com","create_password":"newpassword123","confirm_password":"newpassword123"}'
  ```

### Postman
For each endpoint:
- **Method**: POST
- **URL**: `http://127.0.0.1:7877/<endpoint>` (e.g., `/api/v1/forget-password/`).
- **Headers**:
  - `Content-Type: application/json`
  - `Origin: http://localhost:3000`
- **Body** (raw JSON): Use the example payload.
- No cookies are set, but check **Response** for JSON output.

## Development Notes
- **Environment**: Configured for development (HTTP, no `Secure` cookies). Works with `http://localhost:3000`.
- **Production**:
  - Update base URL to HTTPS.
  - Ensure email settings (e.g., SMTP) are configured for OTP delivery.
- **Password Reset Flow**:
  - Must follow: `/api/v1/forget-password/` → `/api/v1/verify-otp/` → `/api/v1/reset-password/`.
  - Reset requires a valid OTP (10-minute expiry), preventing unauthorized changes.
- **OTP Email**:
  - Styled with coffee-colored background, golden-white gradient text, and a logo.
  - Includes username (e.g., `ugr_2025_3`), email, and OTP.
- **Error Handling**:
  - Always check `error.response.data.errors` to avoid undefined errors.
  - Use field-specific errors for form validation, `general` for alerts.

## Troubleshooting
- **401/403 Errors**: Verify `withCredentials: true` and CSRF token if needed.
- **CORS Issues**: Ensure React runs on `http://localhost:3000`.
- **OTP Issues**:
  - “Invalid OTP”: Verify the code entered.
  - “OTP has expired” or “No valid OTP”: Restart with `/api/v1/forget-password/`.
- **Email Not Sent**: Confirm backend email settings (e.g., SMTP configuration).
- **Password Reset Fails**:
  - Ensure `/api/v1/forget-password/` and `/api/v1/verify-otp/` were called first.
  - Check `errors.general` for OTP-related issues and restart if needed.

## Security Notes
- **OTP Security**: OTPs expire after 10 minutes and are deleted after a successful password reset.
- **No Cookies**: These endpoints don’t set cookies, keeping them lightweight.
- **CSRF**: Include CSRF tokens if 403 errors occur.

### Explanation
- **Scope**:
  - Documents only `/api/v1/forget-password/`, `/api/v1/verify-otp/`, and `/api/v1/reset-password/`.
  - Excludes registration and login as requested.
- **Frontend-Friendly**:
  - Avoids backend jargon (e.g., DRF, OTP model).
  - Explains Axios setup, response handling, and error display in simple terms.
  - Guides on UI flow: email input → OTP input → password reset form.
- **Foundational Steps**:
  - Install Axios, structure JSON payloads, use `withCredentials: true`.
  - Handle success (`message`) and errors (`errors.email`, `errors.general`).
  - Emphasizes sequence: forget password → verify OTP → reset password.
- **Testing**:
  - Includes provided PowerShell commands for all endpoints.
  - Adds cURL for broader compatibility.
  - Suggests Postman for manual testing with JSON verification.
- **Consistency**:
  - Matches your setup: `http://127.0.0.1:7877`, `ugr_2025_3` usernames, no cookies in these endpoints.
  - Error format: `{"errors": {...}}`.
  - Reflects fixed `/api/v1/reset-password/` (requires valid OTP).
- **OTP Email**:
  - Coffee background, golden-white gradient text, logo (placeholder).
- **Security**:
  - OTP validation ensures secure resets.
  - 10-minute OTP expiry, deleted post-reset.
  - No `Secure`/`SameSite` for development; add for production.

### Notes
- **Save As**: `sharfund_password_reset_api_readme.md`.
- **Usage**: Share with frontend developers to guide password reset integration.
- **Production**: Update base URL to HTTPS, configure SMTP for emails.
- **Bug Fix**: `/api/v1/reset-password/` requires OTP, preventing unauthorized resets.
- **Memories**: Builds on your forget password and reset bug fix requests (April 14, 2025).