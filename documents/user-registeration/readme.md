### SharFund JWT Registration API


# SharFund JWT Registration API

This document outlines how to integrate the SharFund registration API in a React frontend using Axios. The API allows users to register with an email, password, address, and mobile number, returning user details and setting authentication tokens as cookies. This guide is designed for frontend developers unfamiliar with backend integration, focusing on foundational steps to make API requests and handle responses.

## API Overview

- **Endpoint**: `POST /api/v1/register/`
- **Purpose**: Creates a new user account.
- **Base URL**: `http://127.0.0.1:7877` (development server; replace with production URL as needed).
- **Content-Type**: `application/json`
- **Authentication**: None required (public endpoint).

## Request Format

The API expects a JSON payload with the following fields:

| Field              | Type   | Required | Description                                      |
|--------------------|--------|----------|--------------------------------------------------|
| `email`            | String | Yes      | User’s email (must be unique, e.g., `user3@example.com`). |
| `password`         | String | Yes      | Password (minimum 8 characters, e.g., `securepassword123`). |
| `confirm_password` | String | Yes      | Must match `password`.                           |
| `address`          | String | No       | User’s address (e.g., `123 Main St`).            |
| `mobile_number`    | String | No       | Phone number (digits with optional `+`, e.g., `+1234567890`). |

**Example Payload**:
```json
{
    "email": "user3@example.com",
    "password": "securepassword123",
    "confirm_password": "securepassword123",
    "address": "123 Main St",
    "mobile_number": "+1234567890"
}
```

## Response Format

### Success (HTTP 201 Created)
- **Body**:
  ```json
  {
      "message": "User registered successfully",
      "user": {
          "username": "ugr_2025_3",
          "email": "user3@example.com",
          "address": "123 Main St",
          "mobile_number": "+1234567890"
      }
  }
  ```
  - `username`: Auto-generated (e.g., `ugr_2025_3`), unique per year.
- **Cookies**:
  - `access_token`: JWT for authentication (1-hour lifespan, `HttpOnly`).
  - `refresh_token`: JWT for refreshing access token (1-day lifespan, `HttpOnly`).

### Error (HTTP 400 Bad Request)
- **Body**:
  ```json
  {
      "errors": {
          "email": ["This email is already registered."],
          "confirm_password": ["Passwords do not match."],
          "password": ["Password must be at least 8 characters long."],
          "mobile_number": ["Mobile number must contain only digits and an optional '+' prefix."],
          "general": ["Failed to create user: ..."]
      }
  }
  ```
  - Errors are field-specific or under `general` for non-field issues.

## Integration Steps for React with Axios

### 1. Install Axios
Ensure Axios is installed in your React project:
```bash
npm install axios
```

### 2. Make the Registration Request
Send a `POST` request to `/api/v1/register/` with the JSON payload. Include `withCredentials: true` to handle cookies.

**Example**:
```javascript
import axios from 'axios';

const registerUser = async (formData) => {
    try {
        const response = await axios.post(
            'http://127.0.0.1:7877/api/v1/register/',
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
const formData = {
    email: 'user3@example.com',
    password: 'securepassword123',
    confirm_password: 'securepassword123',
    address: '123 Main St',
    mobile_number: '+1234567890'
};
registerUser(formData)
    .then(data => console.log('Success:', data))
    .catch(error => console.error('Error:', error));
```

### 3. Handle Cookies
- The API sets `access_token` and `refresh_token` as `HttpOnly` cookies.
- You don’t need to access them directly; the browser includes them in subsequent requests to `http://127.0.0.1:7877` (e.g., protected endpoints or `/api/v1/token/refresh/`).
- To verify cookies:
  - Open Chrome/Firefox Developer Tools (`F12`).
  - Go to **Application** > **Cookies** > `http://127.0.0.1:7877`.
  - Look for `access_token` and `refresh_token`.

### 4. Handle Responses
- **Success**:
  - Display `data.message` (e.g., “User registered successfully”).
  - Use `data.user` (e.g., show `username` or `email` in the UI).
- **Error**:
  - Parse `error.errors` to show field-specific messages (e.g., next to form inputs).
  - Example: If `errors.email` exists, show “This email is already registered” near the email field.

### 5. CORS Considerations
- The API allows requests from `http://localhost:3000`. Ensure your React app runs on this origin.
- Always include `withCredentials: true` to send/receive cookies.

### 6. CSRF Protection
- The API may require a CSRF token for POST requests. If you encounter 403 errors:
  - Fetch the CSRF token from the `csrftoken` cookie or a dedicated endpoint.
  - Include it in headers:
    ```javascript
    axios.defaults.xsrfCookieName = 'csrftoken';
    axios.defaults.xsrfHeaderName = 'X-CSRFToken';
    ```

## Testing the API

### cURL
```bash
curl -X POST http://127.0.0.1:7877/api/v1/register/ -H "Content-Type: application/json" -H "Origin: http://localhost:3000" -d '{"email":"user3@example.com","password":"securepassword123","confirm_password":"securepassword123","address":"123 Main St","mobile_number":"+1234567890"}'
```

### PowerShell
```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:7877/api/v1/register/" -Method POST -Headers @{"Content-Type"="application/json";"Origin"="http://localhost:3000"} -Body '{"email":"user3@example.com","password":"securepassword123","confirm_password":"securepassword123","address":"123 Main St","mobile_number":"+1234567890"}'
```

### Postman
- **Method**: POST
- **URL**: `http://127.0.0.1:7877/api/v1/register/`
- **Headers**:
  - `Content-Type: application/json`
  - `Origin: http://localhost:3000`
- **Body** (raw JSON): Copy the example payload.
- Check **Cookies** tab for `access_token` and `refresh_token`.

## Development Notes
- **Environment**: The API is configured for development (HTTP, no `Secure` cookies). Cookies work with `http://localhost:3000`.
- **Production**: The API will use HTTPS and secure cookies. Update the base URL and test with your production frontend origin.
- **Error Handling**: Always check `error.response.data.errors` to avoid undefined errors in your UI logic.

## Troubleshooting
- **401/403 Errors**: Ensure `withCredentials: true` and correct `Origin` header. Check CSRF token if required.
- **CORS Issues**: Verify your React app runs on `http://localhost:3000`.
- **Duplicate Email**: The API enforces unique emails. Prompt users to use a different email or log in.

### Notes
- **Login**:
  - Payload: `login` (email or username), `password`.
  - Fixed to support both via custom backend (previous issue resolved).
- **Development**:
  - Assumes API runs on `http://127.0.0.1:7877`.
  - For production, update URLs and re-enable `secure=True`, `samesite='Strict'`.

