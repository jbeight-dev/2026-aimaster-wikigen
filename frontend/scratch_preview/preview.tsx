import { createRoot } from 'react-dom/client';
import { MessageBubble } from '../src/components/chat/MessageBubble';
import '../src/index.css';

const answerText = `쿼리 모니터링은 아래 방법으로 할 수 있습니다.

1. 현재 FE 노드에서 실행 중인 쿼리 확인
\`\`\`sql
show proc '/current_queries'
\`\`\`
- 현재 FE 노드에서 실행 중인 쿼리를 보여줍니다.
- 확인 가능한 정보: QueryId, ConnectionId, Database, User, ScanBytes, ScanRows, MemoryUsage, DiskSpillSize, CPUTime, ExecTime, Warehouse, CustomQueryId, ResourceGroup, QueryType

2. 모든 FE 노드에서 실행 중인 쿼리 확인
\`\`\`sql
show proc '/global_current_queries'
\`\`\`
- 모든 FE 노드에서 실행 중인 쿼리 정보를 표시합니다.
- 이 명령은 버전 3.4부터 지원됩니다.

3. Query Queue 상태 확인
\`\`\`sql
SHOW RUNNING QUERIES
\`\`\`
- Query Queue 상태를 주로 확인할 때 사용합니다.
- 쿼리가 큐에 있으면 상태가 \`PENDING\`으로 표시됩니다.
`;

const root = createRoot(document.getElementById('root')!);
root.render(
  <div style={{ maxWidth: 900, margin: '40px auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
    <MessageBubble
      message={{ message_id: '1', role: 'user', text: '쿼리 모니터링 방법', source_document_ids: [] } as any}
      sourceTitles={[]}
    />
    <MessageBubble
      message={{ message_id: '2', role: 'assistant', text: answerText, source_document_ids: [] } as any}
      sourceTitles={['running_queries']}
    />
  </div>
);
