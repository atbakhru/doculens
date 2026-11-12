#include <opencv2/opencv.hpp>
#include <chrono>
#include <iostream>
#include <string>

// Experimental CLI. Input must be the same normalized grayscale PNG used by Python.
int main(int argc, char** argv) {
    if (argc != 3) { std::cerr << "usage: doculens-extract INPUT.png OUTPUT.yml\n"; return 2; }
    cv::setNumThreads(1);
    cv::setRNGSeed(17);
    auto image = cv::imread(argv[1], cv::IMREAD_GRAYSCALE);
    if (image.empty() || image.total() > 24000000) { std::cerr << "invalid image\n"; return 1; }
    auto start = std::chrono::steady_clock::now();
    std::vector<cv::KeyPoint> keys;
    cv::Mat descriptors;
    cv::SIFT::create(600)->detectAndCompute(image, cv::noArray(), keys, descriptors);
    double milliseconds = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now()-start).count();
    cv::FileStorage output(argv[2], cv::FileStorage::WRITE);
    if (!output.isOpened()) { std::cerr << "cannot write output\n"; return 1; }
    output << "opencv_version" << CV_VERSION << "keypoints" << static_cast<int>(keys.size());
    output << "descriptors" << descriptors << "duration_ms" << milliseconds;
    std::cout << "{\"keypoints\":" << keys.size() << ",\"duration_ms\":" << milliseconds << "}\n";
    return 0;
}
