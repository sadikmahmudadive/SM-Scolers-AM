const CLOUD_NAME = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME;

export function getCloudinaryUrl(publicId, options = {}) {
  const { width, height, quality = "auto", format = "auto" } = options;
  let transforms = `f_${format},q_${quality}`;
  if (width) transforms += `,w_${width}`;
  if (height) transforms += `,h_${height}`;
  return `https://res.cloudinary.com/${CLOUD_NAME}/image/upload/${transforms}/${publicId}`;
}

export async function uploadToCloudinary(file, folder = "sm-scolers") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("upload_preset", "sm_scolers_unsigned");
  formData.append("folder", folder);
  formData.append("resource_type", "auto");

  const res = await fetch(
    `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/auto/upload`,
    { method: "POST", body: formData }
  );

  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}
