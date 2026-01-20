# Use the official Playwright image which includes Python and browsers
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory
WORKDIR /app

# Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Install the specific browser binary for your scraper
RUN playwright install chromium

# Command to run your bot
CMD ["python", "main.py"]