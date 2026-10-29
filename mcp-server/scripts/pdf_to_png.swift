// Rasterise every page of a PDF to PNG (macOS PDFKit). Usage: swift pdf_to_png.swift in.pdf outprefix
import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
guard args.count == 3, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("usage: pdf_to_png in.pdf outprefix\n".data(using: .utf8)!)
    exit(2)
}
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.bounds(for: .mediaBox)
    let scale: CGFloat = 1.6
    let size = NSSize(width: box.width * scale, height: box.height * scale)
    let img = NSImage(size: size)
    img.lockFocus()
    NSColor.white.set()
    NSRect(origin: .zero, size: size).fill()
    let ctx = NSGraphicsContext.current!.cgContext
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    img.unlockFocus()
    if let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
       let png = rep.representation(using: .png, properties: [:]) {
        try? png.write(to: URL(fileURLWithPath: String(format: "%@-%02d.png", args[2], i + 1)))
    }
}
print("pages=\(doc.pageCount)")
