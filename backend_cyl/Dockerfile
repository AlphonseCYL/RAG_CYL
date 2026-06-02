FROM python:3.11.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

RUN apt-get update --fix-missing || apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    python3-dev \
    make \
    libgl1 \
    libgl1-mesa-glx \
    libglu1-mesa \
    libglib2.0-0

RUN pip config set global.extra-index-url "https://mirrors.cernet.edu.cn/pypi/web/simple" && \
    pip install --upgrade pip setuptools wheel

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
