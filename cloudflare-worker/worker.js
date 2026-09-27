const IMAGE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b";

const ALLOWED_ASPECT_RATIOS = {
  "1:1": { width: 1024, height: 1024 },
  "4:5": { width: 1024, height: 1280 },
  "9:16": { width: 1024, height: 1820 },
  "16:9": { width: 1820, height: 1024 },
  "3:4": { width: 1024, height: 1365 },
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function unauthorized() {
  return jsonResponse(
    {
      success: false,
      error: "Unauthorized",
    },
    401
  );
}

export default {
  async fetch(request, env) {
    try {
      if (request.method !== "POST") {
        return jsonResponse(
          {
            success: false,
            error: "Only POST requests are allowed",
          },
          405
        );
      }

      const authorization = request.headers.get("Authorization");

      if (!authorization) {
        return unauthorized();
      }

      const expectedAuthorization = `Bearer ${env.API_KEY}`;

      if (authorization !== expectedAuthorization) {
        return unauthorized();
      }

      if (!env.AI) {
        console.error("Workers AI binding 'AI' is not configured");

        return jsonResponse(
          {
            success: false,
            error: "Workers AI binding is not configured",
          },
          500
        );
      }

      let body;

      try {
        body = await request.json();
      } catch {
        return jsonResponse(
          {
            success: false,
            error: "Request body must be valid JSON",
          },
          400
        );
      }

      const prompt = typeof body?.prompt === "string" ? body.prompt.trim() : "";

      if (!prompt) {
        return jsonResponse(
          {
            success: false,
            error: "Prompt is required",
          },
          400
        );
      }

      if (prompt.length > 8000) {
        return jsonResponse(
          {
            success: false,
            error: "Prompt is too long",
          },
          400
        );
      }

      const aspectRatio = typeof body?.aspect_ratio === "string" ? body.aspect_ratio : "1:1";
      const dimensions = ALLOWED_ASPECT_RATIOS[aspectRatio];

      if (!dimensions) {
        return jsonResponse(
          {
            success: false,
            error: "Unsupported aspect ratio",
            allowed_aspect_ratios: Object.keys(ALLOWED_ASPECT_RATIOS),
          },
          400
        );
      }

      console.log(
        JSON.stringify({
          event: "image_generation_started",
          model: IMAGE_MODEL,
          aspect_ratio: aspectRatio,
          width: dimensions.width,
          height: dimensions.height,
        })
      );

      const form = new FormData();
      form.append("prompt", prompt);
      form.append("width", String(dimensions.width));
      form.append("height", String(dimensions.height));

      const formResponse = new Response(form);
      const formStream = formResponse.body;
      const formContentType = formResponse.headers.get("content-type");

      const result = await env.AI.run(IMAGE_MODEL, {
        multipart: {
          body: formStream,
          contentType: formContentType,
        },
      });

      if (!result || !result.image) {
        console.error("Workers AI returned no image");

        return jsonResponse(
          {
            success: false,
            error: "Image generation returned no image",
          },
          502
        );
      }

      let binaryString;

      try {
        binaryString = atob(result.image);
      } catch {
        console.error("Failed to decode generated image");

        return jsonResponse(
          {
            success: false,
            error: "Invalid image returned by Workers AI",
          },
          502
        );
      }

      const imageBytes = new Uint8Array(binaryString.length);

      for (let index = 0; index < binaryString.length; index += 1) {
        imageBytes[index] = binaryString.charCodeAt(index);
      }

      console.log(
        JSON.stringify({
          event: "image_generation_completed",
          aspect_ratio: aspectRatio,
          width: dimensions.width,
          height: dimensions.height,
        })
      );

      return new Response(imageBytes, {
        status: 200,
        headers: {
          "Content-Type": "image/jpeg",
          "Cache-Control": "no-store",
          "X-AdGenie-Aspect-Ratio": aspectRatio,
          "X-AdGenie-Width": String(dimensions.width),
          "X-AdGenie-Height": String(dimensions.height),
        },
      });
    } catch (error) {
      console.error(
        "Image generation error:",
        error instanceof Error ? error.message : String(error)
      );

      return jsonResponse(
        {
          success: false,
          error: "Image generation failed",
        },
        500
      );
    }
  },
};