# ACI Maintenance Tool - Customer Deployment Image
FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools for customer environment
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    openssh-client \
    git \
    curl \
    vim \
    nano \
    iputils-ping \
    net-tools \
    tree \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create customer user
RUN useradd -m -s /bin/bash -G sudo customer && \
    echo 'customer ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Set working directory
WORKDIR /aci-tool

# Copy application files
COPY . .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Make scripts executable
RUN chmod +x *.sh *.py

# Set up proper ownership
RUN chown -R customer:customer /aci-tool

# Switch to customer user
USER customer

# Set up directories
RUN mkdir -p /home/customer/.ssh && \
    chmod 700 /home/customer/.ssh

# Default command keeps container running
CMD ["sleep", "infinity"]
