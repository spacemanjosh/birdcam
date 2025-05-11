from find_birds import find_birds_and_save_clips
from pathlib import Path
import time
import pandas as pd

if __name__ == "__main__":


    main_dir = Path("test")
    input_file = main_dir / "birdcam_20250429_090357.mp4"
    

    models = [
        "yolov5n",
        "yolov5s"
    ]

    output_rates = [
        1,
        2,
        4,
        8
    ]

    # Create a pandas DataFrame to store the results
    results_df = pd.DataFrame(columns=["Model", "Output Rate", "Processing Time (s)"])

    for model_name in models:
        for output_rate in output_rates:
            print(f"Processing with {model_name} at {output_rate} fps")
            output_path = main_dir / f"clips_{model_name}_{output_rate}fps"
            output_path.mkdir(parents=True, exist_ok=True)

            # Time the results
            start_time = time.time()
            find_birds_and_save_clips(
                input_file, 
                output_path=output_path,
                output_rate=output_rate, 
                model_name=model_name, 
                confidence_threshold=0.3)
            end_time = time.time()
            print(f"Processing took {end_time - start_time:.2f} seconds.")

            # Append the results to the DataFrame
            results_temp_df = pd.DataFrame({
                "Model": [model_name],
                "Output Rate": [output_rate],
                "Processing Time (s)": [end_time - start_time]
            })
            results_df = pd.concat([results_df, results_temp_df], ignore_index=True)
    
    # Save the results to a CSV file
    results_df.to_csv(main_dir / "processing_times.csv", index=False)

