export default function DemoPreviewPage() {
  return (
    <iframe
      title="JLPT Listening Studio — interactive design preview"
      src={`${import.meta.env.BASE_URL}studio-preview.html`}
      style={{
        position: "fixed",
        inset: 0,
        display: "block",
        width: "100vw",
        height: "100dvh",
        border: 0,
      }}
    />
  );
}
