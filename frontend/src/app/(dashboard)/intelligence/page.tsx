'use client';

import React, { useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge';
import { VectorSearchResult } from '@/types';
import { Search, Cpu, Sparkles, AlertTriangle, ExternalLink } from 'lucide-react';
import Link from 'next/link';

const EXAMPLE_QUERIES = [
  'Show previous incidents where multiple people entered using one badge',
  'Find incidents involving restricted entrance areas',
  'High risk incidents with low detection confidence',
  'Tailgating incidents in the north lobby',
  'Incidents with more than two unmatched crossings',
];

export default function IntelligencePage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<VectorSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [limit, setLimit] = useState(8);
  const [threshold, setThreshold] = useState(0.0);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<VectorSearchResult[]>('/api/vector/search', {
        method: 'POST',
        body: JSON.stringify({ query: query.trim(), limit, threshold }),
      });
      setResults(data);
      setSearched(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Vector Intelligence"
        subtitle="Incident similarity search backed by vector embeddings and the Qdrant vector store"
      />
      <div className="flex-1 overflow-y-auto p-6">
        {/* Search Header */}
        <Card className="mb-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-100 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Natural Language Incident Search</h2>
              <p className="text-xs text-slate-500">
                Incidents are encoded as 384-dimensional embeddings using sentence-transformers.
                Results ranked by cosine similarity.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && search()}
                placeholder="e.g. multiple people entered with one badge at north entrance…"
                className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={limit}
                onChange={e => setLimit(Number(e.target.value))}
                className="text-xs border border-slate-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {[5, 8, 10, 15, 20].map(v => <option key={v} value={v}>Top {v}</option>)}
              </select>
              <button
                onClick={search}
                disabled={!query.trim() || loading}
                className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-2 whitespace-nowrap"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                Search
              </button>
            </div>
          </div>

          {/* Example Queries */}
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-slate-400">Try:</span>
            {EXAMPLE_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => setQuery(q)}
                className="text-xs px-2.5 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full hover:bg-indigo-100 transition-colors"
              >
                {q.length > 55 ? q.slice(0, 55) + '…' : q}
              </button>
            ))}
          </div>
        </Card>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-4">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Results */}
        {searched && !loading && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-slate-700">
                {results.length} result{results.length !== 1 ? 's' : ''} for &quot;{query}&quot;
              </p>
              <p className="text-xs text-slate-400">Sorted by cosine similarity ↓</p>
            </div>

            {results.length === 0 ? (
              <Card className="text-center py-10">
                <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-slate-500 text-sm">No matching incidents found.</p>
                <p className="text-xs text-slate-400 mt-1">Try a broader query or lower the similarity threshold.</p>
              </Card>
            ) : (
              <div className="space-y-3">
                {results.map((r, i) => (
                  <Card key={r.incident_id} className="hover:border-indigo-300 transition-colors">
                    <div className="flex items-start gap-4">
                      {/* Similarity Score */}
                      <div className="flex flex-col items-center shrink-0 w-14">
                        <div className={`text-lg font-black ${
                          r.similarity_score >= 0.8 ? 'text-indigo-600' :
                          r.similarity_score >= 0.6 ? 'text-blue-600' :
                          r.similarity_score >= 0.4 ? 'text-slate-600' : 'text-slate-400'
                        }`}>
                          {(r.similarity_score * 100).toFixed(0)}%
                        </div>
                        <div className="text-[10px] text-slate-400 font-medium">similarity</div>
                        <div className="mt-1 w-10 h-1 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full"
                            style={{ width: `${r.similarity_score * 100}%` }}
                          />
                        </div>
                        <div className="text-[10px] text-slate-300 mt-1">#{i + 1}</div>
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <SeverityBadge severity={r.severity} />
                          <StatusBadge status={r.status} />
                          <span className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded-full">
                            {r.incident_type.replace('_', ' ')}
                          </span>
                          <span className="text-xs font-bold text-slate-700 ml-auto">Risk: {r.risk_score}</span>
                        </div>
                        <div className="flex gap-3 text-xs text-slate-500 mb-2">
                          <span className="font-medium text-slate-700">{r.gate_name ?? '—'}</span>
                          {r.site_name && <span>· {r.site_name}</span>}
                          {r.created_at && (
                            <span className="ml-auto">
                              {new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed">{r.summary}</p>
                      </div>

                      {/* Link */}
                      <Link
                        href={`/incidents/${r.incident_id}`}
                        className="shrink-0 p-2 rounded-lg bg-slate-50 border border-slate-200 hover:bg-indigo-50 hover:border-indigo-300 transition-colors text-slate-400 hover:text-indigo-600"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Empty state before first search */}
        {!searched && !loading && (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center mx-auto mb-4">
              <Cpu className="w-8 h-8 text-indigo-500" />
            </div>
            <h3 className="text-slate-700 font-semibold mb-2">Semantic Search Ready</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Enter a natural language description of the security pattern you&apos;re looking for.
              The system uses vector embeddings to find semantically similar incidents.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
