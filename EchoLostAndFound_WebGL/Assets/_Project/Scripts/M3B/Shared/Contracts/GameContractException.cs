using System;

namespace EchoLostAndFound.Shared.Contracts
{
    /// <summary>
    /// DataSchema §7 error codes. Only codes that the client-side M3-B modules can
    /// legitimately produce are listed; the full server set is documented in
    /// Docs/DataSchema.md and remains owned by the backend.
    /// </summary>
    public static class ErrorCodes
    {
        public const string InvalidRequest = "INVALID_REQUEST";
        public const string ValidationError = "VALIDATION_ERROR";
        public const string NotFound = "NOT_FOUND";
        public const string PreconditionFailed = "PRECONDITION_FAILED";
        public const string RequestTooLarge = "REQUEST_TOO_LARGE";
        public const string TurnBusy = "TURN_BUSY";
        public const string TurnExpired = "TURN_EXPIRED";
        public const string InteractionExpired = "INTERACTION_EXPIRED";
        public const string ChoiceAlreadyCommitted = "CHOICE_ALREADY_COMMITTED";
        public const string SaveIncompatible = "SAVE_INCOMPATIBLE";
        public const string SaveCorrupt = "SAVE_CORRUPT";
    }

    /// <summary>
    /// A contract violation carrying a DataSchema error code and the HTTP status the
    /// backend would use. Client-side modules throw this instead of returning ad-hoc
    /// strings so Unity integration can surface the same refresh/denial behaviour.
    /// </summary>
    public sealed class GameContractException : Exception
    {
        public GameContractException(string code, string message, int httpStatus, bool retryable = false)
            : base(message)
        {
            Code = code ?? ErrorCodes.ValidationError;
            HttpStatus = httpStatus;
            Retryable = retryable;
        }

        public string Code { get; }

        public int HttpStatus { get; }

        public bool Retryable { get; }

        public static GameContractException InvalidRequest(string message)
        {
            return new GameContractException(ErrorCodes.InvalidRequest, message, 400);
        }

        public static GameContractException Validation(string message)
        {
            return new GameContractException(ErrorCodes.ValidationError, message, 422);
        }

        public static GameContractException NotFound(string message)
        {
            return new GameContractException(ErrorCodes.NotFound, message, 404);
        }

        public static GameContractException Precondition(string message)
        {
            return new GameContractException(ErrorCodes.PreconditionFailed, message, 409);
        }

        public static GameContractException TurnExpired(string message)
        {
            return new GameContractException(ErrorCodes.TurnExpired, message, 410);
        }

        public static GameContractException SaveIncompatible(string message)
        {
            return new GameContractException(ErrorCodes.SaveIncompatible, message, 409);
        }

        public static GameContractException SaveCorrupt(string message)
        {
            return new GameContractException(ErrorCodes.SaveCorrupt, message, 422);
        }

        public static GameContractException RequestTooLarge(string message)
        {
            return new GameContractException(ErrorCodes.RequestTooLarge, message, 413);
        }

        public override string ToString()
        {
            return "GameContractException[" + Code + "/" + HttpStatus + "]: " + Message;
        }
    }
}
