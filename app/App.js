import { useState, useRef } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

// Same-origin by default: app.py serves this web build AND the /ask API
// from one Flask process, so the web version needs no configured host at
// all. Only a native (Android/iOS) build - which runs on-device, with no
// "origin" of its own - would need a real absolute URL here once this app
// has a real deployed backend URL (not yet deployed as of this scaffold).
const BACKEND_URL = Platform.OS === 'web' ? '' : 'https://seers.koroai.org';

const DISCLAIMER =
  "I'm the Seer's Apprentice - I carry real, sourced research about Norse and " +
  'Celtic tradition, but I’m not a druid, skald, filí, bard, völva, or goði, ' +
  'and I never claim to be. Where popular symbols are later folklore rather than ' +
  'historical-period tradition, I say so plainly instead of presenting them as ancient.';

export default function App() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  const ask = async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    const userMessage = { role: 'user', text: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion('');
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Something went wrong.');
      }
      setMessages((prev) => [...prev, { role: 'apprentice', text: data.answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'error', text: `Couldn't get an answer: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.title}>The Seer's Apprentice</Text>
        <Text style={styles.disclaimer}>{DISCLAIMER}</Text>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.messages}
        >
          {messages.length === 0 && (
            <Text style={styles.empty}>
              Ask about Norse or Celtic tradition - e.g. "what is Yggdrasil?" or
              "what does Clan Gunn's own tradition say about its Norse origins?"
            </Text>
          )}
          {messages.map((m, i) => (
            <View
              key={i}
              style={[
                styles.bubble,
                m.role === 'user' ? styles.userBubble : styles.apprenticeBubble,
                m.role === 'error' && styles.errorBubble,
              ]}
            >
              <Text style={m.role === 'user' ? styles.userText : styles.apprenticeText}>
                {m.text}
              </Text>
            </View>
          ))}
          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color="#8aa6c1" />
              <Text style={styles.loadingText}>Thinking, grounded in real sources...</Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Ask a question..."
            placeholderTextColor="#7a8ba0"
            value={question}
            onChangeText={setQuestion}
            onSubmitEditing={ask}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} onPress={ask} disabled={loading}>
            <Text style={styles.sendButtonText}>Ask</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0f1826' },
  flex: { flex: 1 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2f42',
  },
  title: { fontSize: 20, fontWeight: '700', color: '#e8edf4' },
  disclaimer: { fontSize: 12, color: '#8aa6c1', marginTop: 6, lineHeight: 17 },
  messages: { padding: 16, paddingBottom: 24 },
  empty: { color: '#5f7996', fontSize: 14, marginTop: 24, textAlign: 'center' },
  bubble: { borderRadius: 12, padding: 12, marginBottom: 10, maxWidth: '90%' },
  userBubble: { backgroundColor: '#2b4a6b', alignSelf: 'flex-end' },
  apprenticeBubble: { backgroundColor: '#16233780', alignSelf: 'flex-start', borderWidth: 1, borderColor: '#1f2f42' },
  errorBubble: { backgroundColor: '#3a1f22', borderColor: '#7a3a3f' },
  userText: { color: '#fff', fontSize: 15 },
  apprenticeText: { color: '#dbe4ef', fontSize: 15, lineHeight: 21 },
  loadingRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  loadingText: { color: '#8aa6c1', fontSize: 13 },
  inputRow: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#1f2f42',
    backgroundColor: '#0f1826',
    alignItems: 'flex-end',
  },
  input: {
    flex: 1,
    backgroundColor: '#162337',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1f2f42',
    paddingHorizontal: 12,
    paddingVertical: 10,
    maxHeight: 120,
    fontSize: 15,
    color: '#e8edf4',
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: '#2b4a6b',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  sendButtonText: { color: '#fff', fontWeight: '600' },
});
