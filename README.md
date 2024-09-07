# FastAPI Auth Service

This project is a FastAPI-based authentication and user management service designed to run on Vercel's serverless platform. It provides robust user authentication and management functionalities in a scalable, serverless environment.

## Features

- User registration and login
- JWT-based authentication
- Password reset functionality
- Email notifications
- Role-based access control
- Database integration with SQLAlchemy and SQLModel

## Prerequisites

- Python 3.8+
- Docker and Docker Compose (for containerized deployment)
- PostgreSQL

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/teebarg/auth.git
   cd fastapi-auth-service
   ```

2. Install dependencies:
   ```
   make install
   ```

3. Set up environment variables:
   Copy the `.env.example` file to `.env` and fill in the required values.

4. Initialize the database:
   ```
   make db-migrate
   ```

## Running the Application

### Development

To run the application in development mode:
