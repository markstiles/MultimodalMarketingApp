import { AuthGate } from "@/components/AuthGate";
import { ChatPanel } from "@/components/ChatPanel";

export default function Home() {
  return (
    <main className="h-full">
      <AuthGate>
        <ChatPanel />
      </AuthGate>
    </main>
  );
}
