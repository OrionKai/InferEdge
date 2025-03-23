use image;
use std::env;
use std::fs::File;
use std::io::Read;
use tch::{nn, Device, Kind, Tensor};
mod imagenet_classes;

pub fn main() {
    let args: Vec<String> = env::args().collect();
    let model_bin_name: &str = &args[1];
    let image_name: &str = &args[2];

    println!("Loading model");
    let model = tch::CModule::load(model_bin_name)
        .unwrap_or_else(|e| panic!("Failed to load model: {:?}", e));
    println!("Loaded model");

    // Load a tensor that precisely matches the graph input tensor 
    let tensor_data = image_to_tensor(image_name.to_string(), 224, 224);
    //println!("Read input tensor, size in bytes: {}", tensor_data.len());

    // Execute the inference.
    let output_tensor = model.forward_ts(&[tensor_data]).unwrap();
    println!("Executed model inference");

    // Retrieve the output.
    let mut output_buffer = vec![0f32; output_tensor.numel() as usize];
    let output_len = output_buffer.len(); // Store length before mutable borrow
    output_tensor
        .view(-1)
        .copy_data(&mut output_buffer, output_len);


    let results = sort_results(&output_buffer);
    for i in 0..5 {
        println!(
            "   {}.) [{}]({:.4}){}",
            i + 1,
            results[i].0,
            results[i].1,
            imagenet_classes::IMAGENET_CLASSES[results[i].0]
        );
    }
}

// Sort the buffer of probabilities. The graph places the match probability for each class at the
// index for that class (e.g. the probability of class 42 is placed at buffer[42]). Here we convert
// to a wrapping InferenceResult and sort the results.
fn sort_results(buffer: &[f32]) -> Vec<InferenceResult> {
    let mut results: Vec<InferenceResult> = buffer
        .iter()
        .enumerate()
        .map(|(c, p)| InferenceResult(c, *p))
        .collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    results
}

// Take the image located at 'path', open it, resize it to height x width, and then converts
// the pixel precision to FP32. The resulting tensor is then returned.
fn image_to_tensor(path: String, height: u32, width: u32) -> tch::Tensor {
    let mut file_img = File::open(path).unwrap();
    let mut img_buf = Vec::new();
    file_img.read_to_end(&mut img_buf).unwrap();
    let img = image::load_from_memory(&img_buf).unwrap().to_rgb8();
    let resized =
        image::imageops::resize(&img, width, height, ::image::imageops::FilterType::Triangle);
    let mut flat_img: Vec<f32> = Vec::new();
    for rgb in resized.pixels() {
        flat_img.push((rgb[0] as f32 / 255.0 - 0.485) / 0.229);
        flat_img.push((rgb[1] as f32 / 255.0 - 0.456) / 0.224);
        flat_img.push((rgb[2] as f32 / 255.0 - 0.406) / 0.225);
    }

    let tensor = tch::Tensor::of_slice(&flat_img)
        .view([1, height as i64, width as i64, 3]);
    let tensor = tensor.permute(&[0, 3, 1, 2]); // Convert to [1, 3, H, W]
    
    return tensor;
}

// A wrapper for class ID and match probabilities.
#[derive(Debug, PartialEq)]
struct InferenceResult(usize, f32);
