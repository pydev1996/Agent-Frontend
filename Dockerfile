FROM python:3.12-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    build-essential

# Add Microsoft GPG key
RUN curl https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor \
    | tee /usr/share/keyrings/microsoft-prod.gpg > /dev/null

# Correct repo for Debian 11 (bullseye)
RUN echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" \
    > /etc/apt/sources.list.d/mssql-release.list

# Install SQL Server ODBC Driver 18
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Install Python requirements
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
