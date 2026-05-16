import 'dart:convert';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';

class ApiService {
  static String get baseUrl => AppConfig.baseUrl;
  static const Duration _requestTimeout = Duration(seconds: 12);

  static Future<Map<String, String>> _getHeaders() async {
    final token = await FirebaseAuth.instance.currentUser
        ?.getIdToken(true)
        .timeout(_requestTimeout);
    return {
      'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  static Future<void> _cacheUser(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    final userId = data['user_id'] ?? data['id'];
    if (userId is int) {
      await prefs.setInt('user_id', userId);
    } else if (userId is num) {
      await prefs.setInt('user_id', userId.toInt());
    }
    await prefs.setString('user_email', data['email']?.toString() ?? '');
    await prefs.setString('user_name', data['full_name']?.toString() ?? '');
    await prefs.setString('user_role', data['role']?.toString() ?? 'student');
  }

  static Future<Map<String, dynamic>?> login(
    String email,
    String password,
  ) async {
    try {
      await FirebaseAuth.instance.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      final response = await http.get(
        Uri.parse('$baseUrl/auth/me'),
        headers: await _getHeaders(),
      ).timeout(_requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await _cacheUser(data);
        return data;
      }
      debugPrint(
        'Backend /auth/me failed: ${response.statusCode} ${response.body}',
      );
      await FirebaseAuth.instance.signOut();
      return null;
    } catch (e) {
      debugPrint('Login error: $e');
      await FirebaseAuth.instance.signOut();
      return null;
    }
  }

  static Future<Map<String, dynamic>?> register(
    String fullName,
    String email,
    String password,
  ) async {
    try {
      final credential = await FirebaseAuth.instance
          .createUserWithEmailAndPassword(email: email, password: password);
      await credential.user?.updateDisplayName(fullName);
      final response = await http.post(
        Uri.parse('$baseUrl/auth/register-profile'),
        headers: await _getHeaders(),
        body: jsonEncode({'full_name': fullName}),
      ).timeout(_requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await _cacheUser(data);
        return data;
      }
      debugPrint(
        'Backend /auth/register-profile failed: ${response.statusCode} ${response.body}',
      );
    } catch (e) {
      debugPrint('Register error: $e');
      await FirebaseAuth.instance.signOut();
    }
    return null;
  }

  static Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/auth/me'),
        headers: await _getHeaders(),
      ).timeout(_requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await _cacheUser(data);
        return data;
      }
      debugPrint(
        'Backend /auth/me failed: ${response.statusCode} ${response.body}',
      );
    } catch (e) {
      debugPrint('Current user load error: $e');
    }
    return null;
  }

  static Future<bool> updateCurrentUser(String fullName) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/auth/me'),
        headers: await _getHeaders(),
        body: jsonEncode({'full_name': fullName}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await FirebaseAuth.instance.currentUser?.updateDisplayName(fullName);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('user_name', data['full_name'] ?? fullName);
        return true;
      }
    } catch (_) {}
    return false;
  }

  static Future<String?> changePassword(
    String currentPassword,
    String newPassword,
  ) async {
    try {
      final user = FirebaseAuth.instance.currentUser;
      final email = user?.email;
      if (user == null || email == null) {
        return 'No Firebase user is signed in.';
      }
      final credential = EmailAuthProvider.credential(
        email: email,
        password: currentPassword,
      );
      await user.reauthenticateWithCredential(credential);
      await user.updatePassword(newPassword);
      return null;
    } catch (e) {
      debugPrint('Change password error: $e');
      return 'Unable to update password with Firebase Auth.';
    }
  }

  static Future<void> logout() async {
    await FirebaseAuth.instance.signOut();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_id');
    await prefs.remove('user_email');
    await prefs.remove('user_name');
    await prefs.remove('user_role');
  }

  static Future<Map<String, dynamic>?> getProfile(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/gamification/profile/$userId'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getUserAttempts(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/quizzes/user/$userId/attempts'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getCourses() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getLessons(int courseId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/$courseId/lessons'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> getCourseContentMap(int courseId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/$courseId/content-map'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getCourseProgressSummary() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/progress/summary'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> getCourseProgress(int courseId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/courses/$courseId/progress'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getQuiz(int lessonId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/quizzes/lesson/$lessonId'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> submitQuiz(
    int quizId,
    List<int> answers,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/quizzes/$quizId/submit'),
        headers: await _getHeaders(),
        body: jsonEncode({'answers': answers}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<String> getAiHint(
    int userId,
    String question, {
    String context = 'General',
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/hint'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'context': context,
          'user_question': question,
        }),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['hint'];
      }
      return "I'm having trouble connecting to my knowledge base right now.";
    } catch (e) {
      return "Network error: Unable to reach AI Tutor.";
    }
  }

  static Future<Map<String, dynamic>?> getAiMistakeReview(
    int userId,
    String lessonTitle,
    List<Map<String, dynamic>> wrongAnswers,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/review-mistakes'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'lesson_title': lessonTitle,
          'wrong_answers': wrongAnswers,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<String> askAiReviewFollowUp(
    int userId,
    String lessonTitle,
    List<Map<String, dynamic>> wrongAnswers,
    String userQuestion,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/review-chat'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'user_id': userId,
          'lesson_title': lessonTitle,
          'wrong_answers': wrongAnswers,
          'user_question': userQuestion,
        }),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['answer']?.toString() ??
            'I could not generate an explanation.';
      }
    } catch (_) {}
    return 'I could not generate an explanation right now. Please try again.';
  }

  static Future<Map<String, dynamic>?> getTeacherDashboard() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/dashboard'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getStudentsProgress() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/students-progress'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getTeacherAttempts() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/recent-attempts'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> getTeacherAnalyticsSummary() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/analytics-summary'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getTeacherAssignments() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/assignments'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<Map<String, dynamic>?> createTeacherAssignment({
    required int quizId,
    required int courseId,
    required String title,
    required String instructions,
    String? dueAt,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/assignments'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'quiz_id': quizId,
          'course_id': courseId,
          'title': title,
          'instructions': instructions,
          'due_at': dueAt,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> updateTeacherAssignment({
    required int assignmentId,
    required int quizId,
    required int courseId,
    required String title,
    required String instructions,
    String? dueAt,
  }) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/teacher/assignments/$assignmentId'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'quiz_id': quizId,
          'course_id': courseId,
          'title': title,
          'instructions': instructions,
          'due_at': dueAt,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> publishTeacherAssignment(
    int assignmentId,
  ) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/teacher/assignments/$assignmentId/publish'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  // Teacher Content Management
  static Future<Map<String, dynamic>?> createCourse(
    String title,
    String description,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/courses'),
        headers: await _getHeaders(),
        body: jsonEncode({'title': title, 'description': description}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createLesson(
    int courseId,
    String title,
    String content,
    int order,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/lessons'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'course_id': courseId,
          'title': title,
          'content': content,
          'order': order,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createQuiz(
    int lessonId,
    String title,
    List<dynamic> questions,
    int xpReward,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/quizzes'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'lesson_id': lessonId,
          'title': title,
          'questions': questions,
          'xp_reward': xpReward,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getUsers() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/users'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<bool> toggleUserStatus(int userId, bool active) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/users/$userId/status?active=$active'),
        headers: await _getHeaders(),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<bool> changeUserRole(int userId, String role) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/users/$userId/role?role=$role'),
        headers: await _getHeaders(),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<Map<String, dynamic>?> getSystemConfig() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/config'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<bool> updateSystemConfig(
    bool aiSafety,
    bool retries,
    int xp,
  ) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/admin/config'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'ai_safety': aiSafety,
          'retries_enabled': retries,
          'xp_per_quiz': xp,
        }),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<Map<String, dynamic>?> getPlatformStatus() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/admin/platform-status'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getAppConfig() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/config'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createOpenQuestionSession(
    int courseId,
    int lessonId, {
    String? message,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/open-question/sessions'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'course_id': courseId,
          'lesson_id': lessonId,
          'message': message,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> sendOpenQuestionMessage(
    int sessionId,
    String message,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/open-question/sessions/$sessionId/message'),
        headers: await _getHeaders(),
        body: jsonEncode({'message': message}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getStudentAiSession(int sessionId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/ai-tutor/sessions/$sessionId'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> createQuizExplanationSession(
    int attemptId, {
    int? questionIndex,
    String? message,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/quiz-explanation/sessions'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'attempt_id': attemptId,
          'question_index': questionIndex,
          'message': message,
        }),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> sendQuizExplanationMessage(
    int sessionId,
    String message,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/ai-tutor/quiz-explanation/sessions/$sessionId/message'),
        headers: await _getHeaders(),
        body: jsonEncode({'message': message}),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>?> getAnalyticsOverview() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/analytics/overview'),
        headers: await _getHeaders(),
      );
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>> createEModeSession({
    required int courseId,
    required int lessonId,
    required String topic,
    required String instructions,
    String? studentLevel,
    String? difficulty,
    String? language,
    int? taskCount,
    List<String> preferredTypes = const [],
    String? quizTitle,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/e-mode/sessions'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'course_id': courseId,
          'lesson_id': lessonId,
          'topic': topic,
          'instructions': instructions,
          'student_level': studentLevel,
          'difficulty': difficulty,
          'language': language,
          'task_count': taskCount,
          'preferred_types': preferredTypes,
          'quiz_title': quizTitle,
        }),
      );
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to create Quiz AI Creator session: $e'};
    }
  }

  static Future<Map<String, dynamic>> getEModeSession(int sessionId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/teacher/e-mode/sessions/$sessionId'),
        headers: await _getHeaders(),
      );
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to load Quiz AI Creator session: $e'};
    }
  }

  static Future<Map<String, dynamic>> uploadEModeMaterial({
    required int sessionId,
    required String fileName,
    required List<int> bytes,
  }) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/teacher/e-mode/sessions/$sessionId/upload'),
      );
      final headers = await _getHeaders();
      headers.remove('Content-Type');
      request.headers.addAll(headers);
      request.files.add(
        http.MultipartFile.fromBytes('file', bytes, filename: fileName),
      );
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to upload learning material: $e'};
    }
  }

  static Future<Map<String, dynamic>> generateEModeDraft(int sessionId) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/e-mode/sessions/$sessionId/generate'),
        headers: await _getHeaders(),
      );
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to generate Quiz AI Creator draft: $e'};
    }
  }

  static Future<Map<String, dynamic>> chatEModeSession({
    required int sessionId,
    required String message,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/e-mode/sessions/$sessionId/chat'),
        headers: await _getHeaders(),
        body: jsonEncode({'message': message}),
      );
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to update Quiz AI Creator draft: $e'};
    }
  }

  static Future<Map<String, dynamic>> saveEModeDraft({
    required int sessionId,
    String? title,
    int? xpReward,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/teacher/e-mode/sessions/$sessionId/save'),
        headers: await _getHeaders(),
        body: jsonEncode({
          'title': title,
          'xp_reward': xpReward,
        }),
      );
      return _decodeJsonOrError(response);
    } catch (e) {
      return {'error': 'Unable to save Quiz AI Creator draft: $e'};
    }
  }

  static Map<String, dynamic> _decodeJsonOrError(http.Response response) {
    if (response.body.isEmpty) {
      return response.statusCode >= 200 && response.statusCode < 300
          ? {}
          : {'error': 'Unexpected empty response (${response.statusCode})'};
    }

    try {
      final decoded = jsonDecode(response.body);
      if (response.statusCode >= 200 && response.statusCode < 300) {
        return decoded is Map<String, dynamic>
            ? decoded
            : {'data': decoded};
      }
      if (decoded is Map<String, dynamic>) {
        return {'error': decoded['detail']?.toString() ?? 'Request failed'};
      }
      return {'error': 'Request failed with status ${response.statusCode}'};
    } catch (_) {
      return {
        'error': 'Request failed with status ${response.statusCode}',
      };
    }
  }
}
