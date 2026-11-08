// Offline OCR substitute. Apple Vision, not Google Cloud Vision/Document AI.
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count == 2 else {
    fatalError("Usage: swift ocr.swift receipt.png")
}
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US"]
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: input, options: [:])
try handler.perform([request])
let lines = (request.results ?? []).compactMap { observation -> [String: Any]? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    return ["text": candidate.string, "confidence": candidate.confidence]
}
let result: [String: Any] = ["engine": "Apple Vision VNRecognizeTextRequest", "is_google_cloud_vision": false, "network_required": false, "synthetic_input": true, "lines": lines]
let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
print(String(data: data, encoding: .utf8)!)
