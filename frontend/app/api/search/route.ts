import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q');

    if (!query) {
      return NextResponse.json({ error: 'Query parameter "q" is required' }, { status: 400 });
    }

    const includeKufar = searchParams.get('include_kufar');
    const backendUrl = `${BACKEND_URL}/api/search?q=${encodeURIComponent(query)}${includeKufar === 'true' ? '&include_kufar=true' : ''}`;
    const response = await fetch(backendUrl);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Backend request failed' }));
      return NextResponse.json(errorData, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Search API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', detail: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
