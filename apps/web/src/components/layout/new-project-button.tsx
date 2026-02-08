'use client';

import { Button } from "@/components/ui/button";
import { PlusCircle } from "lucide-react";
import { useProjectStore } from "@/lib/stores/project-store";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

export function NewProjectButton() {
    const reset = useProjectStore((state) => state.reset);
    const setStep = useProjectStore((state) => state.setStep);
    const router = useRouter();

    const handleNewProject = () => {
        reset();
        setStep(1);
        router.push('/projects/new');
        toast.success('Started a new project');
    };

    return (
        <Button
            variant="outline"
            size="sm"
            onClick={handleNewProject}
            className="ml-auto flex items-center gap-2"
        >
            <PlusCircle className="h-4 w-4" />
            <span className="hidden sm:inline">New Project</span>
        </Button>
    );
}
