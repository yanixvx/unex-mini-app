import Foundation
import Vision
import AppKit

let path = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "latex_box.png"
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERROR: cannot load image \(path)")
    exit(1)
}

let request = VNRecognizeTextRequest { req, err in
    guard let observations = req.results as? [VNRecognizedTextObservation] else { return }
    if observations.isEmpty {
        print("NO_TEXT_FOUND: на изображении не обнаружено ни одной надписи")
    } else {
        print("TEXT_FOUND: \(observations.count) надписей:")
        for obs in observations {
            if let top = obs.topCandidates(1).first {
                print("  - \"\(top.string)\" (confidence: \(top.confidence))")
            }
        }
    }
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US", "uk-UA", "ru-RU"]

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([request])
