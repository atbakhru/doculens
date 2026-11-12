FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends cmake g++ libopencv-dev python3-opencv python3-numpy && rm -rf /var/lib/apt/lists/*
WORKDIR /native
COPY native/vision .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2
CMD ["python3", "parity.py"]
