// 本地 macOS Vision OCR（离线、免费、中文）。
// 用法: ocr_vision <图片路径>   -> 逐行打印识别文字（已按从上到下、同行从左到右排序）
// 编译: swiftc -framework Vision -framework AppKit -framework CoreGraphics ocr_vision.swift -o ocr_vision
import Vision
import AppKit
import Foundation

let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image: \(path)\n".data(using: .utf8)!)
    exit(1)
}

let req = VNRecognizeTextRequest { req, _ in
    guard let obs = req.results as? [VNRecognizedTextObservation] else { return }
    // boundingBox 原点在左下；按“从上到下、同高度从左到右”还原阅读顺序
    let sorted = obs.sorted { a, b in
        let ya = a.boundingBox.origin.y, yb = b.boundingBox.origin.y
        if abs(ya - yb) > 0.012 { return ya > yb }
        return a.boundingBox.origin.x < b.boundingBox.origin.x
    }
    for o in sorted {
        if let s = o.topCandidates(1).first?.string, !s.isEmpty { print(s) }
    }
}
req.recognitionLanguages = ["zh-Hans", "en-US"]
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do { try handler.perform([req]) } catch {
    FileHandle.standardError.write("vision perform failed: \(error)\n".data(using: .utf8)!)
    exit(2)
}
