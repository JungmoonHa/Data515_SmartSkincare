# Examples: Quality of the Example of Using the Package

This folder provides a step-by-step guide and screenshots for using the Smart Skincare recommendation tool, aligned with the "Quality of the example of using the package" criterion. Add your own screenshots as `example_images/example_image_1.jpg` through `example_image_12.jpg` and fill in the sections below.

---

## Running our Tests

Copy the `test_app.py` file (or the relevant test file for this project) and in the terminal run:

```bash
python <copied file path>
```

You should see that the tests pass.

---

## Home Page

Begin by reading the "Tutorial For Using the Tool" section in the main [README](../README.md) file. Open terminal and get started with the app.

---

## [Feature / Tab name – e.g. Skin Type Input]

Navigate to this tab by clicking it. Describe the main actions (e.g. select skin type, optional concerns).

Example: select "Combination" and "Sensitive", then click to get recommendations.

![Figure_1](example_images/example_image_1.jpg)

You can also hover on elements to see more details.

![Figure_2](example_images/example_image_2.jpg)

---

## [Next section – e.g. Recommendation Results]

Describe how to interpret the results. Example: top products list and score explanation.

![Figure_3](example_images/example_image_3.jpg)

Single click on a product to see details.

![Figure_4](example_images/example_image_4.jpg)

Double clicking can [describe behavior].

![Figure_5](example_images/example_image_5.jpg)

If you do not see results, check that your inputs are valid (e.g. skin type selected, product filters within range).

---

## [Next section – e.g. Ingredient Analysis / Predictor]

Describe inputs (e.g. skin type, product, optional filters). Example: select skin type and optionally product category; click "Get Recommendations".

![Figure_6](example_images/example_image_6.jpg)

The tool shows the predicted score and short analysis. Try changing inputs to explore.

**What if I don’t select a required field?**

A validation message will appear.

![Figure_7](example_images/example_image_7.jpg)

This applies even if other fields are filled.

![Figure_8](example_images/example_image_8.jpg)

Optional fields (e.g. product category) can be left empty.

![Figure_9](example_images/example_image_9.jpg)

Explore other cases; as long as required fields are set and values are in the allowed range, the tool will return results.

**Input limits**

If a value is out of range (e.g. rating filter > 5), the app will show an error.

![Figure_10](example_images/example_image_10.jpg)

When a multi-select allows at most N options, selecting one more will prompt: "You can only select up to N options. Remove an option first."

![Figure_11](example_images/example_image_11.jpg)

**Search / autocomplete**

You can type in dropdowns to filter options and find items by partial name.

![Figure_12](example_images/example_image_12.jpg)

---

We hope you find this tool useful!
