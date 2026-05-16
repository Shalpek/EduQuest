import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';

typedef CreateOpenQuestionSession =
    Future<Map<String, dynamic>?> Function(
      int courseId,
      int lessonId,
      String? message,
    );
typedef SendOpenQuestionMessage =
    Future<Map<String, dynamic>?> Function(int sessionId, String message);

class AITutorScreen extends StatefulWidget {
  final int courseId;
  final String courseTitle;
  final int lessonId;
  final String lessonTitle;
  final int userId;
  final CreateOpenQuestionSession? createSession;
  final SendOpenQuestionMessage? sendMessage;

  const AITutorScreen({
    required this.courseId,
    required this.courseTitle,
    required this.lessonId,
    required this.lessonTitle,
    required this.userId,
    this.createSession,
    this.sendMessage,
    super.key,
  });

  @override
  State<AITutorScreen> createState() => _AITutorScreenState();
}

class _AITutorScreenState extends State<AITutorScreen> {
  final TextEditingController _ctl = TextEditingController();
  final List<Map<String, String>> _messages = [];
  bool _isTyping = false;
  bool _isInitializing = true;
  int? _sessionId;
  String? _error;

  CreateOpenQuestionSession get _createSession =>
      widget.createSession ??
      ((courseId, lessonId, message) => ApiService.createOpenQuestionSession(
        courseId,
        lessonId,
        message: message,
      ));

  SendOpenQuestionMessage get _sendMessageRequest =>
      widget.sendMessage ?? ApiService.sendOpenQuestionMessage;

  @override
  void initState() {
    super.initState();
    _messages.add({
      'role': 'ai',
      'text':
          'Ask about ${widget.lessonTitle}. I will answer from the selected lesson first and the course context second.',
    });
    _initializeSession();
  }

  Future<void> _initializeSession() async {
    final session = await _createSession(
      widget.courseId,
      widget.lessonId,
      null,
    );
    if (!mounted) return;

    setState(() {
      _sessionId = session?['session_id'] as int?;
      _isInitializing = false;
      if (_sessionId == null) {
        _error =
            'The AI tutor session could not start. Check the backend and try again.';
      }
    });
  }

  Future<void> _sendPrompt(String prompt) async {
    if (_sessionId == null) {
      setState(() {
        _error =
            'The tutor session is unavailable right now. Retry after the backend is ready.';
        _isTyping = false;
      });
      return;
    }

    final response = await _sendMessageRequest(_sessionId!, prompt);
    if (!mounted) return;

    setState(() {
      if (response == null || response['answer'] == null) {
        _messages.add({
          'role': 'ai',
          'text':
              'I could not generate a grounded answer right now. Please try again.',
        });
        _error = 'No AI answer was returned by the backend.';
      } else {
        _messages.add({
          'role': 'ai',
          'text': response['answer'].toString(),
        });
        _error = null;
      }
      _isTyping = false;
    });
  }

  Future<void> _sendMessage() async {
    if (_ctl.text.trim().isEmpty || _isTyping || _isInitializing) return;

    final prompt = _ctl.text.trim();
    setState(() {
      _messages.add({'role': 'user', 'text': prompt});
      _isTyping = true;
      _ctl.clear();
    });

    await _sendPrompt(prompt);
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Tutor')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: AppSurface(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const AppInfoChip(
                    label: 'Lesson-grounded support',
                    color: EduQuestColors.info,
                    icon: Icons.smart_toy_outlined,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    widget.lessonTitle,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    widget.courseTitle,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Ask for a simpler explanation, examples, summaries, or quiz preparation. Active quiz answers are intentionally blocked.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    AppStatusBanner(
                      message: _error!,
                      color: EduQuestColors.danger,
                      icon: Icons.error_outline,
                    ),
                  ],
                ],
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length + ((_isTyping || _isInitializing) ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length) return _buildTypingIndicator();
                final m = _messages[index];
                final isUser = m['role'] == 'user';
                return Align(
                  alignment:
                      isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.8,
                    ),
                    decoration: BoxDecoration(
                      color:
                          isUser
                              ? EduQuestColors.primary
                              : EduQuestColors.surface,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(20),
                        topRight: const Radius.circular(20),
                        bottomLeft:
                            isUser ? const Radius.circular(20) : Radius.zero,
                        bottomRight:
                            isUser ? Radius.zero : const Radius.circular(20),
                      ),
                    ),
                    child: Text(
                      m['text']!,
                      style: const TextStyle(fontSize: 15, height: 1.45),
                    ),
                  ),
                );
              },
            ),
          ),
          SafeArea(
            top: false,
            child: Container(
              padding: const EdgeInsets.all(16),
              color: Colors.transparent,
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctl,
                      minLines: 1,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText: 'Ask about this lesson...',
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 56,
                    height: 56,
                    child: ElevatedButton(
                      onPressed:
                          (_isTyping || _isInitializing) ? null : _sendMessage,
                      style: ElevatedButton.styleFrom(
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                        padding: EdgeInsets.zero,
                      ),
                      child: const Icon(Icons.send),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    final text =
        _isInitializing
            ? 'Starting lesson AI session...'
            : 'AI Tutor is thinking...';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          text,
          style: const TextStyle(color: EduQuestColors.textMuted),
        ),
      ),
    );
  }
}
