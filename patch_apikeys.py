import re

with open("G:\Scrrapi\frontend\src\pages\ApiKeys.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Fix double import of SkeletonTable if exists
content = re.sub(r'import { SkeletonTable } from "../components/neo/Skeleton";\nimport { SkeletonTable } from "../components/neo/Skeleton";', 'import { SkeletonTable } from "../components/neo/Skeleton";', content)

# Remove TableSkeleton component
content = re.sub(r'function TableSkeleton\(\) \{[\s\S]*?\}\n\nfunction CreateKeyModal', 'function CreateKeyModal', content)

# Replace <TableSkeleton /> usage
content = content.replace("<TableSkeleton />", "<div style={{ maxWidth: 1126 }}><SkeletonTable rows={4} columns={8} /></div>")

with open("G:\Scrrapi\frontend\src\pages\ApiKeys.tsx", "w", encoding="utf-8") as f:
    f.write(content)

