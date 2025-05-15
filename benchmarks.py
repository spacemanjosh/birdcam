from find_birds import find_birds_and_save_clips
from birdcam_pipeline import process_videos_from_day
from pathlib import Path
import time
import pandas as pd

if __name__ == "__main__":

    thresholds = [0.3]

    input_path = Path("/bird_drive/recordings")
    input_file = input_path / "birdcam_20250429_090357.mp4"
    test_dir = Path("/bird_drive/test")
    test_dir.mkdir(parents=True, exist_ok=True)
    

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

    dates = [
        "20250429",
        "20250511",
    ]

    # Create a pandas DataFrame to store the results
    results_df = pd.DataFrame(columns=["Model", "Output Rate", "Processing Time (s)"])

    for model_name in models:
        for output_rate in output_rates:
            for threshold in thresholds:
                main_dir = test_dir / f"test_{threshold}threshold_no_vase"

                print(f"Processing with {model_name} at {output_rate} fps")
                output_path = main_dir / f"clips_{model_name}_{output_rate}fps"
                output_path.mkdir(parents=True, exist_ok=True)

                # Time the results
                start_time = time.time()
                # find_birds_and_save_clips(
                #     input_file, 
                #     output_path=output_path,
                #     output_rate=output_rate, 
                #     model_name=model_name, 
                #     confidence_threshold=threshold)
                
                for date in dates:
                    print(f"Processing date: {date}")
                    # Process videos from the specified day
                    process_videos_from_day(
                        date=date,
                        video_path=Path("/Volumes/Cosmos/birdcam/videos/v2"),
                        output_path=output_path,
                        output_rate=output_rate,
                        confidence_threshold=threshold
                    )

                end_time = time.time()
                print(f"Processing took {end_time - start_time:.2f} seconds.")

                # Append the results to the DataFrame
                results_temp_df = pd.DataFrame({
                    "Model": [model_name],
                    "Output Rate": [output_rate],
                    "Threshold": [threshold],
                    "Processing Time (s)": [end_time - start_time]
                })
                results_df = pd.concat([results_df, results_temp_df], ignore_index=True)
    
    # Save the results to a CSV file
    results_df.to_csv(test_dir / "processing_times.csv", index=False)

