import { cn } from "@/lib/utils";

type DivProps = React.HTMLAttributes<HTMLDivElement>;
export const Card = ({ className, ...p }: DivProps) => <div className={cn("rounded-md border bg-card shadow-sm", className)} {...p} />;
export const CardHeader = ({ className, ...p }: DivProps) => <div className={cn("p-4 pb-2", className)} {...p} />;
export const CardTitle = ({ className, ...p }: DivProps) => <h3 className={cn("font-semibold leading-tight", className)} {...p} />;
export const CardContent = ({ className, ...p }: DivProps) => <div className={cn("p-4 pt-2", className)} {...p} />;
