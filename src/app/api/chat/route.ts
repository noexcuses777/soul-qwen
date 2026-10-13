// Previous provider implementation is deliberately not imported or executed.
// All SOUL inference uses the local FastAPI /api/sessions contract.
export async function POST() {
  return Response.json({ detail: 'SOUL 채팅은 /api/sessions/{id}/ask를 사용하세요.' }, { status: 410 });
}
