# SharFund JWT Login API

This document explains how to integrate the SharFund login API in a React frontend using Axios. The API allows users to log in with either their email or username (e.g., `ugr_2025_3`) and password, returning user details and setting authentication tokens as cookies. This guide is tailored for frontend developers new to backend integration, covering essential steps to make requests and handle responses.

## API Overview

- **Endpoint**: `POST /api/v1/login/`
- **Purpose**: Authenticates a user and provides JWT tokens.
- **Base URL**: `http://127.0.0.1:7877` (development server; replace with production URL as needed).
- **Content-Type**: `application/json`
- **Authentication**: None required (public endpoint).

## Request Format

The API expects a JSON payload with the following fields:

| Field      | Type   | Required | Description                                      |
|------------|--------|----------|--------------------------------------------------|
| `login`    | String | Yes      | Email (e.g., `user3@example.com`) or username (e.g., `ugr_2025_3`). |
| `password` | String | Yes      | User’s password (e.g., `securepassword123`).      |

**Example Payload (Email)**:
```json
{
    "login": "user3@example.com",
    "password": "securepassword123"
}
```

**Example Payload (Username)**:
```json
{
    "login": "ugr_2025_3",
    "password": "securepassword123"
}
```

## Response Format

### Success (HTTP 200 OK)
- **Body**:
  ```json
  {
      "message": "Login successful",
      "user": {
          "username": "ugr_2025_3",
          "email": "user3@example.com",
          "address": "123 Main St",
          "mobile_number": "+1234567890"
      }
  }
  ```
- **Cookies**:
  - `access_token`: JWT for authentication (1-hour lifespan, `HttpOnly`).
  - `refresh_token`: JWT for refreshing access token (1-day lifespan, `HttpOnly`).

### Error (HTTP 400 Bad Request)
- **Body**:
  ```json
  {
      "errors": {
          "general": ["Invalid email/username or password."],
          "login": ["This field is required."],
          "password": ["This field is required."]
      }
  }
  ```
  - Errors are under `general` for invalid credentials or field-specific for missing inputs.

## Integration Steps for React with Axios

### 1. Install Axios
Ensure Axios is installed in your React project:
```bash
npm install axios
```

### 2. Make the Login Request
Send a `POST` request to `/api/v1/login/` with the JSON payload. Include `withCredentials: true` to handle cookies.

**Example**:
```javascript
import axios from 'axios';

const loginUser = async (formData) => {
    try {
        const response = await axios.post(
            'http://127.0.0.1:7877/api/v1/login/',
            formData,
            {
                headers: { 'Content-Type': 'application/json' },
                withCredentials: true
            }
        );
        return response.data; // { message, user }
    } catch (error) {
        throw error.response.data; // { errors }
    }
};

// Usage in your form
const formDataEmail = {
    login: 'user3@example.com',
    password: 'securepassword123'
};
const formDataUsername = {
    login: 'ugr_2025_3',
    password: 'securepassword123'
};
loginUser(formDataEmail)
    .then(data => console.log('Success:', data))
    .catch(error => console.error('Error:', error));
```

### 3. Handle Cookies
- The API sets `access_token` and `refresh_token` as `HttpOnly` cookies.
- These are automatically included in requests to `http://127.0.0.1:7877` (e.g., protected endpoints or `/api/v1/token/refresh/`).
- To verify cookies:
  - Open Chrome/Firefox Developer Tools (`F12`).
  - Go to **Application** > **Cookies** > `http://127.0.0.1:7877`.
  - Look for `access_token` and `refresh_token`.

### 4. Handle Responses
- **Success**:
  - Display `data.message` (e.g., “Login successful”).
  - Use `data.user` to update UI (e.g., show `username` or redirect to dashboard).
- **Error**:
  - Check `error.errors.general` for “Invalid email/username or password” and display it (e.g., below the login form).
  - Handle `error.errors.login` or `error.errors.password` for missing fields.

### 5. CORS Considerations
- The API allows requests from `http://localhost:3000`. Ensure your React app runs on this origin.
- Always use `withCredentials: true` to send/receive cookies.

### 6. CSRF Protection
- If you get 403 errors, the API may require a CSRF token:
  - Fetch the `csrftoken` cookie or a CSRF endpoint.
  - Include it in headers:
    ```javascript
    axios.defaults.xsrfCookieName = 'csrftoken';
    axios.defaults.xsrfHeaderName = 'X-CSRFToken';
    ```

## Testing the API

### cURL
**With Email**:
```bash
curl -X POST http://127.0.0.1:7877/api/v1/login/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"login":"user3@example.com","password":"securepassword123"}'
```

**With Username**:
```bash
curl -X POST http://127.0.0.1:7877/api/v1/login/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"login":"ugr_2025_3","password":"securepassword123"}'
```

### PowerShell
**With Email**:
```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/login/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"login":"user3@example.com","password":"securepassword123"}'
```

**With Username**:
```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/login/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"login":"ugr_2025_3","password":"securepassword123"}'
```

### Postman
- **Method**: POST
- **URL**: `http://127.0.0.1:7877/api/v1/login/`
- **Headers**:
  - `Content-Type: application/json`
  - `Origin: http://localhost:3000`
- **Body** (raw JSON): Use either email or username payload.
- Check **Cookies** tab for `access_token` and `refresh_token`.

## Development Notes
- **Environment**: Configured for development (HTTP, no `Secure` cookies). Works with `http://localhost:3000`.
- **Production**: Will use HTTPS and secure cookies. Update the base URL and test with your production frontend.
- **Login Flexibility**: Users can enter either their email or username (starts with `ugr_`). Ensure your form UI supports this (e.g., label as “Email or Username”).

## Troubleshooting
- **Invalid Credentials**: Verify the user exists (register first) and the password is correct.
- **401/403 Errors**: Check `withCredentials: true` and CSRF token if needed.
- **CORS Issues**: Ensure React runs on `http://localhost:3000`.
- **Cookie Issues**: Use Developer Tools to confirm `access_token` and `refresh_token` are set.


### Explanation
- **Frontend-Friendly**:
  - Avoids backend jargon (e.g., DRF, Simple JWT internals).
  - Explains Axios setup, cookie handling, and error parsing in simple terms.
  - Includes step-by-step integration (install Axios, make request, handle responses).
  - Covers CORS and CSRF, common pitfalls for frontend developers.
- **Foundational Steps**:
  - **Request**: Guides on structuring JSON payloads and headers.
  - **Cookies**: Explains `HttpOnly` cookies and how to verify them without accessing them in code.
  - **Responses**: Details how to use success data and display errors in the UI.
  - **Testing**: Provides cURL, PowerShell, and Postman examples for manual testing.
- **Commands**:
  - Incorporated the provided PowerShell commands, ensuring they match your API (`http://127.0.0.1:7877`).
  - Added equivalent cURL commands for broader compatibility.
- **Consistency**:
  - Matches your setup: `ugr_2025_3` usernames, `HttpOnly` cookies, no `Secure`/`SameSite`, `http://localhost:3000` CORS.
  - Retains error format (`{"errors": {...}}`) and response structure.
- **Separate Files**:
  - Registration and login APIs are documented separately for clarity.
  - Each includes all necessary details without overlap.

### Notes
- **Registration**:
  - Payload: `email`, `password`, `confirm_password`, `address`, `mobile_number`.
  - Username auto-generated (`ugr_2025_3`).
- **Login**:
  - Payload: `login` (email or username), `password`.
  - Fixed to support both via custom backend (previous issue resolved).
- **Development**:
  - Assumes API runs on `http://127.0.0.1:7877`.
  - For production, update URLs and re-enable `secure=True`, `samesite='Strict'`.

