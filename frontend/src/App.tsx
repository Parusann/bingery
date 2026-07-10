import { RouterProvider } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { router } from "./routes";

export default function App() {
  // reducedMotion="user": framer-motion drops transform animations for users
  // with prefers-reduced-motion set (CSS animations are handled in index.css).
  return (
    <MotionConfig reducedMotion="user">
      <RouterProvider router={router} />
    </MotionConfig>
  );
}
